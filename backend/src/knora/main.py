from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
from knora.access.keycloak import KeycloakAuthenticator
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.http.conversations import router as conversations_router
from knora.adapters.http.evaluation_catalog import router as evaluation_catalog_router
from knora.adapters.http.evaluation_datasets import router as evaluation_datasets_router
from knora.adapters.http.evaluation_runs import router as evaluation_runs_router
from knora.adapters.http.evaluation_scoring import router as evaluation_scoring_router
from knora.adapters.http.routes import router as http_router
from knora.adapters.http.tools import router as tools_router
from knora.adapters.http.workspaces import router as workspaces_router
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.object_store.inventory import JsonlObjectInventory
from knora.adapters.object_store.s3 import BotoS3CapabilityClient, S3CapabilityClient, S3ObjectStore
from knora.adapters.pdf.docling import DoclingTextExtractor
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.conversation_store import PostgresConversationStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.evaluation_datasets import PostgresDatasetStore
from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.object_reconciliation import (
    PostgresClock,
    PostgresObjectReferenceResolver,
)
from knora.adapters.postgres.operational_observability import PostgresOperationalMetricsStore
from knora.adapters.postgres.operator_reader import PostgresOperatorReader
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tool_action_store import PostgresToolActionStore
from knora.adapters.postgres.workspace_admission import PostgresWorkspaceAdmissionStore
from knora.adapters.postgres.workspace_store import PostgresWorkspaceStore
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.answering.module import AnswerQuestion
from knora.answering.reranking_configuration import (
    DeploymentRerankingConfigurationResolver,
    RerankingConfigurationResolver,
    resolve_reranking_configuration,
)
from knora.answering.retrieval_configuration import (
    DeploymentRetrievalConfigurationResolver,
    resolve_retrieval_configuration,
)
from knora.api.routes import m5_e2e_router, router
from knora.application.operator_observability import OperatorObservability
from knora.bootstrap import build_provider_selection
from knora.conversations.runner import ConversationRunner
from knora.conversations.service import ConversationService
from knora.domain.errors import KnoraError
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.datasets import DatasetService
from knora.evaluation.pdf_runtime import PdfRuntimeProfile
from knora.evaluation.proposals import ProposalProfile
from knora.evaluation.runs import EvaluationRunService, RuntimeProfile
from knora.evaluation.scoring import EvaluationScoringService, ScoringProfile
from knora.infrastructure.lexical_configuration import load_lexical_population
from knora.infrastructure.settings import ObjectStoreSettings, settings
from knora.ingestion.documents import DocumentLifecycleService, DocumentReader
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    PdfDerivationHandler,
    ProcessIngestionJob,
    RetryPolicyV1,
    SystemRandomSource,
    UuidOperationIds,
)
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfExtractionSubmissionConfiguration,
    PdfSubmissionConfiguration,
)
from knora.ingestion.module import IngestDocument
from knora.ingestion.object_lifecycle import (
    LifecycleClock,
    LifecycleRandomSource,
    ObjectInventory,
    ObjectLifecycleMaintenance,
    ObjectLifecycleReconciler,
    ObjectLifecycleRetryPolicyV1,
    ObjectLifecycleWorker,
    SystemLifecycleRandomSource,
)
from knora.ingestion.object_store import ObjectStore
from knora.ingestion.operational_observability import (
    AlertPolicyV1,
    LoggingOperationalTelemetry,
    OperationalAlertConfigurationV1,
    OperationalMetricsStore,
    OperationalObservability,
    OperationalTelemetry,
)
from knora.ingestion.pdf import PdfExtractionConfiguration, PdfTextExtractor
from knora.ingestion.processing import DocumentProcessor
from knora.ingestion.search_indexing import (
    DerivationJobHandler,
    DynamicSearchIndexHandler,
    LexicalIndexHandler,
)
from knora.providers.cloudflare.pdf_understanding import CloudflarePdfUnderstandingProvider
from knora.providers.cloudflare.reranking import CloudflareRerankingProvider
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.reranking import RerankingProvider
from knora.tools import (
    CapabilityRegistry,
    ExternalScopeBinding,
    HmacDispatchEnvelopeSigner,
    PolicyProvenance,
    ReadTool,
    ReferenceExecutionResourceAuthorizer,
    ReferenceObservationResolver,
    ReferenceProposalTargetVerifier,
    ReferenceVerifier,
    RegistryCapabilityResolver,
    SupportToolGateway,
    ToolActionStore,
)
from knora.tools.lifecycle_projection import ToolLifecycleProjectionReader
from knora.tools.proposal_http import ActorContextProvider
from knora.tools.proposal_http import router as proposal_router
from knora.tools.proposals import ExecutionAuthorizer, WriteProposalWorkflow
from knora.workspaces.ports import WorkspaceAdmissionStore
from knora.workspaces.service import WorkspaceService

_DEFAULT_WORKSPACE_ADMISSIONS = object()


def create_app(
    *,
    ingest_document: IngestDocument | None = None,
    ingestion_jobs: IngestionJobs | None = None,
    document_reader: DocumentReader | None = None,
    document_lifecycle: DocumentLifecycleService | None = None,
    answer_question: AnswerQuestion | None = None,
    reranking_provider: RerankingProvider | None = None,
    reranking_configuration_resolver: RerankingConfigurationResolver | None = None,
    api_key_authenticator: ApiKeyAuthenticator | None = None,
    keycloak_authenticator: KeycloakAuthenticator | None = None,
    embedding_configuration: EmbeddingConfiguration | None = None,
    ingestion_worker: ProcessIngestionJob | None = None,
    object_store: ObjectStore | None = None,
    s3_client: S3CapabilityClient | None = None,
    lifecycle_maintenance: ObjectLifecycleMaintenance | None = None,
    lifecycle_inventory: ObjectInventory | None = None,
    lifecycle_clock: LifecycleClock | None = None,
    lifecycle_random_source: LifecycleRandomSource | None = None,
    operational_metrics_store: OperationalMetricsStore | None = None,
    operational_telemetry: OperationalTelemetry | None = None,
    operational_alert_configuration: OperationalAlertConfigurationV1 | None = None,
    operator_observability: OperatorObservability | None = None,
    evaluation_profiles: tuple[RuntimeProfile, ...] = (),
    evaluation_pdf_profiles: tuple[PdfRuntimeProfile, ...] = (),
    evaluation_proposal_profiles: dict[str, ProposalProfile] | None = None,
    evaluation_scoring_profiles: tuple[ScoringProfile, ...] = (),
    write_proposal_workflow: WriteProposalWorkflow | None = None,
    tool_actor_context_provider: ActorContextProvider | None = None,
    read_tool: ReadTool | None = None,
    tool_capability_registry: CapabilityRegistry | None = None,
    tool_scope_bindings: Mapping[str, ExternalScopeBinding] | None = None,
    tool_reference_verifier: ReferenceVerifier | None = None,
    tool_proposal_policy: PolicyProvenance | None = None,
    tool_action_store: ToolActionStore | None = None,
    tool_lifecycle_reader: ToolLifecycleProjectionReader | None = None,
    tool_execution_authorizer: ExecutionAuthorizer | None = None,
    support_tool_gateway: SupportToolGateway | None = None,
    tool_dispatch_signer: HmacDispatchEnvelopeSigner | None = None,
    workspace_authorizer: WorkspaceAuthorizer | None = None,
    workspace_service: WorkspaceService | None = None,
    workspace_admission_store: WorkspaceAdmissionStore | None | object = (
        _DEFAULT_WORKSPACE_ADMISSIONS
    ),
) -> FastAPI:
    deployed_retrieval_configuration = resolve_retrieval_configuration(
        settings.retrieval_configuration_id, vector_min_similarity=settings.vector_min_similarity
    )
    lexical_population = load_lexical_population(
        deployed_retrieval_configuration, settings.lexical_population_manifest
    )
    if lexical_population is not None and (
        not settings.lexical_qdrant_url or not settings.lexical_qdrant_collection
    ):
        raise ValueError("lexical runtime requires Qdrant URL and collection")
    providers = build_provider_selection(settings)
    selected_embedding_configuration = embedding_configuration or providers.embedding_configuration
    deployed_reranking_configuration = None
    reranking_policy_id = settings.reranking_configuration_id or (
        deployed_retrieval_configuration.reranking_policy_id
        if deployed_retrieval_configuration is not None
        else None
    )
    if reranking_policy_id is not None:
        deployed_reranking_configuration = resolve_reranking_configuration(reranking_policy_id)

    selected_reranking_resolver = reranking_configuration_resolver
    if selected_reranking_resolver is None and deployed_reranking_configuration is not None:
        selected_reranking_resolver = DeploymentRerankingConfigurationResolver(
            deployed_reranking_configuration
        )

    selected_reranking_provider = reranking_provider
    if (
        selected_reranking_provider is None
        and settings.cloudflare_account_id
        and settings.cloudflare_api_token
    ):
        selected_reranking_provider = CloudflareRerankingProvider(
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_api_token.get_secret_value(),
            model=settings.cloudflare_reranker_model,
            timeout_seconds=settings.cloudflare_timeout_seconds,
        )
    lexical_client = None
    lexical_index = None
    if lexical_population is not None:
        lexical_client = httpx.Client(
            base_url=settings.lexical_qdrant_url,
            timeout=10,
            trust_env=False,
        )
        lexical_index = NativeQdrantSearchIndex(
            index=QdrantSearchIndex(settings.lexical_qdrant_collection, lexical_population.profile),
            client=lexical_client,
        )
    elif (
        deployed_retrieval_configuration.strategy in ("dense-only", "hybrid", "bm25-only")
        and bool(settings.lexical_qdrant_url)
        and bool(settings.lexical_qdrant_collection)
    ):
        lexical_client = httpx.Client(
            base_url=settings.lexical_qdrant_url,
            timeout=10,
            trust_env=False,
        )
        lexical_index = NativeQdrantSearchIndex(
            index=QdrantSearchIndex(
                settings.lexical_qdrant_collection,
                profile=None,
                embedding_configuration=selected_embedding_configuration,
            ),
            client=lexical_client,
        )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        del application
        try:
            if lexical_index is not None:
                await run_in_threadpool(lexical_index.ensure_collection)
            yield
        finally:
            if lexical_client is not None:
                lexical_client.close()
            if selected_reranking_provider is not None:
                close_reranking = getattr(selected_reranking_provider, "close", None)
                if close_reranking is not None:
                    close_reranking()
            close_embedding = getattr(providers.embedding_provider, "close", None)
            if close_embedding is not None:
                close_embedding()
            close_generation = getattr(providers.generation_provider, "aclose", None)
            if close_generation is not None:
                await close_generation()

    application = FastAPI(title="Knora Agent", version="0.1.0", lifespan=lifespan)
    use_docling = (
        settings.pdf_parser_driver == "docling"
        and bool(settings.cloudflare_account_id)
        and bool(settings.cloudflare_api_token)
    )
    if use_docling:
        dense_pdf_configuration = PdfSubmissionConfiguration.docling_native(
            embedding_configuration=selected_embedding_configuration
        )
    else:
        dense_pdf_configuration = PdfSubmissionConfiguration.layout_preserving(
            embedding_configuration=selected_embedding_configuration
        )
    application.state.pdf_submission_configuration = (
        PdfExtractionSubmissionConfiguration(
            parser_configuration_id=dense_pdf_configuration.parser_configuration_id,
            normalizer_configuration_id=dense_pdf_configuration.normalizer_configuration_id,
            chunking_configuration=dense_pdf_configuration.chunking_configuration,
            lexical_profile=lexical_population.profile,
        )
        if lexical_population is not None
        else dense_pdf_configuration
    )
    answering_store = PostgresAnsweringStore(
        SessionFactory,
        lexical_index=lexical_index,
        lexical_population=lexical_population,
    )
    workspace_admissions = (
        PostgresWorkspaceAdmissionStore(SessionFactory)
        if workspace_admission_store is _DEFAULT_WORKSPACE_ADMISSIONS
        else workspace_admission_store
    )
    application.state.workspace_admission_store = workspace_admissions
    application.state.answer_question = answer_question or AnswerQuestion(
        embedding_provider=providers.embedding_provider if lexical_population is None else None,
        generation_provider=providers.generation_provider,
        answer_support_verifier=(
            providers.generation_provider.build_answer_support_verifier()
            if hasattr(providers.generation_provider, "build_answer_support_verifier")
            else None
        ),
        store=answering_store,
        embedding_configuration=selected_embedding_configuration
        if lexical_population is None
        else None,
        retrieval_configuration_resolver=DeploymentRetrievalConfigurationResolver(
            deployed_retrieval_configuration
        ),
        reranking_provider=selected_reranking_provider,
        reranking_configuration_resolver=selected_reranking_resolver,
        admission_store=workspace_admissions,
    )
    application.state.ingest_document = ingest_document or IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=providers.embedding_provider,
        store=PostgresIngestionStore(
            SessionFactory,
            search_index_store=PostgresSearchIndexStore(SessionFactory),
            lexical_population=lexical_population,
            lexical_profile=lexical_population.profile if lexical_population is not None else None,
        ),
        admission_store=workspace_admissions,
    )
    runtime_object_store_settings = ObjectStoreSettings.from_runtime(settings)
    selected_object_store = object_store
    if selected_object_store is None and runtime_object_store_settings.backend == "filesystem":
        selected_object_store = FileSystemObjectStore(runtime_object_store_settings.root)
    if selected_object_store is None and runtime_object_store_settings.backend == "s3_compatible":
        if not runtime_object_store_settings.s3_bucket:
            raise ValueError("S3-compatible ObjectStore requires a bucket")
        if s3_client is None:
            if (
                runtime_object_store_settings.s3_access_key is None
                or runtime_object_store_settings.s3_secret_key is None
            ):
                raise ValueError("S3-compatible ObjectStore requires access credentials")
            s3_client = BotoS3CapabilityClient(
                endpoint_url=runtime_object_store_settings.s3_endpoint,
                region_name=runtime_object_store_settings.s3_region,
                access_key=runtime_object_store_settings.s3_access_key.get_secret_value(),
                secret_key=runtime_object_store_settings.s3_secret_key.get_secret_value(),
            )
        selected_object_store = S3ObjectStore(
            client=s3_client,
            bucket=runtime_object_store_settings.s3_bucket,
        )
    if selected_object_store is None:
        raise ValueError("unsupported object_store_backend")
    job_store = PostgresIngestionJobStore(
        SessionFactory,
        retrieval_configuration=deployed_retrieval_configuration,
        lexical_population=lexical_population,
    )
    selected_lifecycle_maintenance = lifecycle_maintenance or job_store
    selected_lifecycle_clock = lifecycle_clock or PostgresClock(SessionFactory)
    application.state.ingestion_jobs = ingestion_jobs or IngestionJobs(
        object_store=selected_object_store,
        store=job_store,
        lifecycle_maintenance=selected_lifecycle_maintenance,
        lifecycle_clock=selected_lifecycle_clock,
        admission_store=workspace_admissions,
        deployed_embedding_configuration=selected_embedding_configuration,
    )
    if (
        settings.pdf_parser_driver == "docling"
        and settings.cloudflare_account_id
        and settings.cloudflare_api_token
    ):
        cf_pdf_provider = CloudflarePdfUnderstandingProvider(
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_api_token.get_secret_value(),
            ocr_model=settings.cloudflare_ocr_model,
            timeout_seconds=settings.cloudflare_timeout_seconds,
        )
        extractor: PdfTextExtractor = DoclingTextExtractor(cf_provider=cf_pdf_provider)
    else:
        extractor = PypdfTextExtractor()

    pdf_handler = PdfDerivationHandler(
        object_store=selected_object_store,
        extractor=extractor,
        embedding_provider=providers.embedding_provider,
        profile_resolver=job_store.pdf_profile_for_work,
        runtime_embedding_configuration=selected_embedding_configuration,
        lexical_population=lexical_population,
    )
    handler = pdf_handler
    if lexical_index is not None:
        handler = DerivationJobHandler(
            pdf_handler=pdf_handler,
            index_handler=LexicalIndexHandler(
                store=PostgresSearchIndexStore(SessionFactory),
                index=lexical_index,
                lexical_population=lexical_population,
            ),
        )
    application.state.ingestion_worker = ingestion_worker or ProcessIngestionJob(
        store=job_store,
        handler=handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
    )
    application.state.search_index_maintenance = (
        DynamicSearchIndexHandler(
            store=PostgresSearchIndexStore(SessionFactory),
            index=lexical_index,
            lexical_policy_id=deployed_retrieval_configuration.lexical_policy_id
            or "lexical-bm25-v1",
            embedding_configuration_id=selected_embedding_configuration.id,
        )
        if lexical_index is not None
        and lexical_population is None
        and (
            deployed_retrieval_configuration.strategy == "dense-only"
            or deployed_retrieval_configuration.fusion_policy_id == "dbsf-v1"
        )
        else None
    )
    application.state.dataset_service = DatasetService(
        store=PostgresDatasetStore(SessionFactory),
        object_store=selected_object_store,
        extractor=PypdfTextExtractor(),
        configuration=PdfExtractionConfiguration.layout_preserving(),
        proposal_profiles=evaluation_proposal_profiles,
    )
    application.state.evaluation_catalog = Milestone3Catalog()
    # Trusted hosts may compose profiles; default wiring remains empty and live admission blocked.
    evaluation_run_store = PostgresEvaluationRunStore(SessionFactory)
    application.state.evaluation_runs = EvaluationRunService(
        catalog=application.state.evaluation_catalog,
        store=evaluation_run_store,
        profiles=evaluation_profiles,
        pdf_profiles=evaluation_pdf_profiles,
        datasets=application.state.dataset_service,
    )
    application.state.evaluation_scoring = EvaluationScoringService(
        application.state.evaluation_runs, evaluation_run_store, evaluation_scoring_profiles
    )
    application.state.object_lifecycle_worker = ObjectLifecycleWorker(
        maintenance=selected_lifecycle_maintenance,
        object_store=selected_object_store,
        retry_policy=ObjectLifecycleRetryPolicyV1(
            random_source=lifecycle_random_source or SystemLifecycleRandomSource()
        ),
    )
    selected_inventory = lifecycle_inventory
    if selected_inventory is None and settings.object_inventory_manifest:
        selected_inventory = JsonlObjectInventory(settings.object_inventory_manifest)
    application.state.object_lifecycle_reconciler = None
    if selected_inventory is not None:
        minimum_age_seconds = settings.object_inventory_minimum_age_seconds
        if minimum_age_seconds is None or minimum_age_seconds < 0:
            raise ValueError(
                "object inventory reconciliation requires a non-negative minimum age setting"
            )
        application.state.object_lifecycle_reconciler = ObjectLifecycleReconciler(
            inventory=selected_inventory,
            references=PostgresObjectReferenceResolver(SessionFactory),
            maintenance=selected_lifecycle_maintenance,
            minimum_age=timedelta(seconds=minimum_age_seconds),
            now=selected_lifecycle_clock,
        )
    selected_alert_configuration = operational_alert_configuration
    if selected_alert_configuration is None and settings.operational_alert_configuration_json:
        selected_alert_configuration = OperationalAlertConfigurationV1.from_json(
            settings.operational_alert_configuration_json
        )
    selected_metrics_store = operational_metrics_store
    if selected_metrics_store is None:
        selected_metrics_store = PostgresOperationalMetricsStore(
            SessionFactory,
            retry_window=timedelta(seconds=settings.operational_metrics_retry_window_seconds),
        )
    application.state.operational_observability = OperationalObservability(
        store=selected_metrics_store,
        telemetry=operational_telemetry or LoggingOperationalTelemetry(),
        alert_policy=AlertPolicyV1() if selected_alert_configuration is not None else None,
        alert_configuration=selected_alert_configuration,
    )
    operator_reader = PostgresOperatorReader(SessionFactory, lexical_population=lexical_population)
    application.state.operator_observability = operator_observability or OperatorObservability(
        trace_reader=operator_reader,
        evaluation_reader=operator_reader,
        operations_reader=selected_metrics_store,
    )
    application.state.api_key_authenticator = api_key_authenticator or ApiKeyAuthenticator(
        credentials_from_json(settings.api_credentials_json)
    )
    selected_document_reader = document_reader or PostgresDocumentReader(
        SessionFactory,
        deployed_embedding_configuration=selected_embedding_configuration,
        deployed_retrieval_configuration=deployed_retrieval_configuration,
        lexical_population=lexical_population,
    )
    application.state.document_reader = selected_document_reader
    application.state.document_lifecycle = document_lifecycle or DocumentLifecycleService(
        selected_document_reader,
        admission_store=workspace_admissions,
    )
    application.state.embedding_configuration = selected_embedding_configuration
    application.state.authenticator = application.state.api_key_authenticator
    if keycloak_authenticator is not None:
        keycloak_authenticator.api_key_authenticator = application.state.api_key_authenticator
    elif settings.keycloak_issuer and settings.keycloak_audience:
        keycloak_authenticator = KeycloakAuthenticator(
            issuer=settings.keycloak_issuer,
            audience=settings.keycloak_audience,
            jwks_url=settings.keycloak_jwks_url,
            jwks_cache_ttl_seconds=settings.keycloak_jwks_cache_ttl_seconds,
            api_key_authenticator=application.state.api_key_authenticator,
        )
    application.state.authenticator = (
        keycloak_authenticator or application.state.api_key_authenticator
    )
    application.state.workspace_authorizer = workspace_authorizer or WorkspaceAuthorizer(
        PostgresWorkspaceStore(SessionFactory)
    )
    application.state.workspace_service = workspace_service or WorkspaceService(
        PostgresWorkspaceStore(SessionFactory)
    )
    conversation_store = PostgresConversationStore(SessionFactory)
    application.state.conversation_store = conversation_store
    application.state.conversation_service = ConversationService(
        store=conversation_store,
        workspace_authorizer=application.state.workspace_authorizer,
    )
    application.state.conversation_runner = ConversationRunner(
        store=conversation_store,
        answer_question=application.state.answer_question,
        result_reader=answering_store,
    )
    selected_tool_action_store = tool_action_store or PostgresToolActionStore(SessionFactory)
    selected_write_proposal_workflow = write_proposal_workflow
    if selected_write_proposal_workflow is None and tool_actor_context_provider is not None:
        if tool_scope_bindings is None or tool_reference_verifier is None:
            raise ValueError(
                "proposal composition requires scope bindings and a reference verifier"
            )
        registry = tool_capability_registry or CapabilityRegistry.static()
        execution_dependencies_complete = all(
            item is not None
            for item in (
                tool_execution_authorizer,
                support_tool_gateway,
                tool_dispatch_signer,
            )
        )
        selected_write_proposal_workflow = WriteProposalWorkflow(
            capability_resolver=RegistryCapabilityResolver(
                registry,
                bindings=tool_scope_bindings,
                policy=tool_proposal_policy or PolicyProvenance(),
            ),
            store=selected_tool_action_store,
            target_verifier=ReferenceProposalTargetVerifier(tool_reference_verifier),
            execution_authorizer=tool_execution_authorizer,
            execution_resource_authorizer=(
                ReferenceExecutionResourceAuthorizer(
                    registry,
                    bindings=tool_scope_bindings,
                    verifier=tool_reference_verifier,
                )
                if execution_dependencies_complete
                else None
            ),
            observation_reference_resolver=(
                ReferenceObservationResolver(
                    bindings=tool_scope_bindings,
                    verifier=tool_reference_verifier,
                )
                if execution_dependencies_complete
                else None
            ),
            gateway=(support_tool_gateway if execution_dependencies_complete else None),
            dispatch_signer=(tool_dispatch_signer if execution_dependencies_complete else None),
        )
    application.state.write_proposal_workflow = selected_write_proposal_workflow
    application.state.tool_actor_context_provider = tool_actor_context_provider

    application.state.read_tool = read_tool
    application.state.tool_lifecycle_reader = (
        tool_lifecycle_reader or ToolLifecycleProjectionReader(selected_tool_action_store)
    )

    @application.exception_handler(KnoraError)
    async def handle_knora_error(request: Request, error: KnoraError) -> JSONResponse:
        status = {
            "UNAUTHENTICATED": 401,
            "WORKSPACE_ACCESS_DENIED": 403,
            "WORKSPACE_ARCHIVED": 409,
            "REVISION_CONFLICT": 409,
            "IDEMPOTENCY_CONFLICT": 409,
            "MISSING_WORKSPACE_REVISION": 428,
            "INVALID_WORKSPACE_REVISION": 422,
            "INVALID_WORKSPACE_NAME": 422,
            "INVALID_WORKSPACE_CURSOR": 422,
            "INVALID_WORKSPACE_LIMIT": 422,
            "INVALID_WORKSPACE_QUERY": 422,
            "INVALID_CONVERSATION_TITLE": 422,
            "INVALID_CONVERSATION_CURSOR": 422,
            "INVALID_CONVERSATION_LIMIT": 422,
            "INVALID_CONVERSATION_QUERY": 422,
            "INVALID_TURN_CURSOR": 422,
            "INVALID_TURN_LIMIT": 422,
            "INVALID_TURN_STAGE": 422,
            "CAPABILITY_ACCESS_DENIED": 403,
            "INVALID_SOURCE_KEY": 400,
            "INVALID_SOURCE_NAME": 400,
            "UNSUPPORTED_DOCUMENT_TYPE": 400,
            "INVALID_DOCUMENT_ENCODING": 400,
            "DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION": 413,
            "DOCUMENT_CONCURRENTLY_UPDATED": 409,
            "REINDEX_REQUIRED": 409,
            "EMBEDDING_DIMENSION_MISMATCH": 502,
            "EMBEDDING_CONFIGURATION_MISMATCH": 502,
            "GENERATION_OUTPUT_INVALID": 502,
            "GENERATION_MODEL_MISMATCH": 502,
            "PROVIDER_REQUEST_FAILED": 502,
            "PROVIDER_RESPONSE_INVALID": 502,
            "PERSISTENCE_OPERATION_FAILED": 500,
            "INVALID_IDEMPOTENCY_KEY": 400,
            "EVALUATION_IDEMPOTENCY_KEY_INVALID": 400,
            "EVALUATION_SELECTION_INVALID": 422,
            "EVALUATION_DATASET_NOT_FOUND": 404,
            "EVALUATION_RUN_NOT_FOUND": 404,
            "EVALUATION_REPORT_UNAVAILABLE": 409,
            "EVALUATION_PREFLIGHT_STALE": 409,
            "EVALUATION_CHECKPOINT_CONFLICT": 409,
            "EVALUATION_ATTEMPT_STALE": 409,
            "EVALUATION_IDEMPOTENCY_CONFLICT": 409,
            "EVALUATION_CASE_NOT_FOUND": 404,
            "EVALUATION_CASE_INVALID": 422,
            "EVALUATION_DATASET_REVISION_CONFLICT": 409,
            "EVALUATION_DATASET_FROZEN": 409,
            "EVALUATION_GOLD_NOT_READY": 409,
            "EVALUATION_PROPOSAL_NOT_READY": 409,
            "EVALUATION_PROPOSAL_REQUEST_CONFLICT": 409,
            "EVALUATION_SCORING_NOT_READY": 409,
            "EVALUATION_GOLD_DIGEST_CONFLICT": 409,
            "EVALUATION_GOLD_VERSION_NOT_FOUND": 404,
            "EVALUATION_REVIEW_DECISION_INVALID": 422,
            "RUNTIME_PROFILE_UNAVAILABLE": 409,
            "RUNTIME_BINDING_UNAVAILABLE": 409,
            "PROVIDER_APPROVAL_REQUIRED": 409,
            "MISSING_IDEMPOTENCY_KEY": 400,
            "INVALID_PDF_SIGNATURE": 400,
            "PDF_STREAM_NOT_SEEKABLE": 400,
            "OBJECT_STORE_METADATA_INVALID": 500,
            "OBJECT_NOT_FOUND": 404,
            "PDF_RESOURCE_LIMIT_EXCEEDED": 413,
            "PDF_INGESTION_NOT_CONFIGURED": 503,
            "LEXICAL_RETRIEVAL_UNAVAILABLE": 503,
            "INGESTION_JOB_NOT_FOUND": 404,
            "DOCUMENT_VERSION_NOT_FOUND": 404,
            "DOCUMENT_NOT_FOUND": 404,
            "SOURCE_OBJECT_NOT_AVAILABLE": 404,
            "OPERATOR_OBSERVATION_NOT_FOUND": 404,
            "OPERATOR_OBSERVATION_FAILED": 503,
            "DOCUMENT_VERSION_NOT_CURRENT": 409,
            "INVALID_CONFIG_MODE": 400,
            "CONFIG_SOURCE_JOB_REQUIRED": 400,
            "CONFIG_SOURCE_JOB_NOT_ALLOWED": 400,
            "CONFIG_SOURCE_JOB_INVALID": 400,
            "CONFIGURATION_NOT_AVAILABLE": 409,
            "IDEMPOTENCY_KEY_CONFLICT": 409,
            "CONVERSATION_BUSY": 409,
            "CONVERSATION_ARCHIVED": 409,
            "CONVERSATION_NOT_FOUND": 404,
            "CONVERSATION_TURN_NOT_FOUND": 404,
            "CONVERSATION_TRACE_CONFLICT": 500,
            "MISSING_CONVERSATION_REVISION": 428,
            "INVALID_CONVERSATION_REVISION": 422,
            "INVALID_QUESTION": 400,
            "INVALID_REQUEST_FINGERPRINT": 400,
            "CONVERSATION_ADMISSION_REQUIRED": 403,
            "CONVERSATION_ADMISSION_MISSING": 500,
            "CONVERSATION_EXECUTION_FAILED": 500,
            "INVALID_CONVERSATION_WORKER_ID": 500,
            "INVALID_TURN_RESULT": 500,
            "TOOL_CAPABILITY_NOT_FOUND": 403,
            "TOOL_APPROVAL_FORBIDDEN": 403,
            "TOOL_RESOURCE_ACCESS_DENIED": 403,
            "TOOL_PROPOSAL_NOT_FOUND": 404,
            "TOOL_REQUEST_INVALID": 422,
            "TOOL_PROPOSAL_ALREADY_DECIDED": 409,
            "TOOL_PROPOSAL_REVISION_CONFLICT": 409,
            "TOOL_PROPOSAL_STALE": 409,
            "TOOL_PROPOSAL_EXPIRED": 409,
            "TOOL_PROPOSAL_NOT_APPROVED": 409,
            "TOOL_EXECUTION_NOT_AUTHORIZED": 403,
            "TOOL_TICKET_NOT_FOUND": 404,
            "INVALID_TOOL_RESOURCE_REFERENCE": 400,
            "TOOL_PROVIDER_UNAVAILABLE": 502,
            "TOOL_PROVIDER_CONTRACT_INVALID": 502,
        }.get(error.code, 400)
        headers = {"Cache-Control": "no-store"}
        if error.code == "CONVERSATION_BUSY":
            headers["Retry-After"] = "2"
        return JSONResponse(
            status_code=status,
            content={"error": {"code": error.code}},
            headers=headers,
        )

    application.include_router(http_router)
    application.include_router(workspaces_router)
    application.include_router(conversations_router)
    application.include_router(evaluation_datasets_router)
    application.include_router(evaluation_catalog_router)
    application.include_router(evaluation_runs_router)
    application.include_router(evaluation_scoring_router)
    application.include_router(router)
    if settings.m5_e2e_faults_enabled:
        from knora.api.m5_e2e_faults import M5E2EFaultController

        application.state.m5_e2e_fault_controller = M5E2EFaultController()
        application.include_router(m5_e2e_router)
    if selected_write_proposal_workflow is not None and tool_actor_context_provider is not None:
        application.include_router(proposal_router)
    if read_tool is not None:
        application.include_router(tools_router)
    return application


app = create_app()
