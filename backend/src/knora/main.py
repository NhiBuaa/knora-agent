from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json
from knora.access.keycloak import KeycloakAuthenticator
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.http.conversations import router as conversations_router
from knora.adapters.http.routes import router as http_router
from knora.adapters.http.tools import router as tools_router
from knora.adapters.http.workspaces import router as workspaces_router
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.object_store.inventory import JsonlObjectInventory
from knora.adapters.object_store.s3 import BotoS3CapabilityClient, S3CapabilityClient, S3ObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.conversation_store import PostgresConversationStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.object_reconciliation import (
    PostgresClock,
    PostgresObjectReferenceResolver,
)
from knora.adapters.postgres.operational_observability import PostgresOperationalMetricsStore
from knora.adapters.postgres.operator_reader import PostgresOperatorReader
from knora.adapters.postgres.tool_action_store import PostgresToolActionStore
from knora.adapters.postgres.workspace_admission import PostgresWorkspaceAdmissionStore
from knora.adapters.postgres.workspace_store import PostgresWorkspaceStore
from knora.answering.module import AnswerQuestion
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
from knora.ingestion.jobs import IngestionJobs
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
from knora.ingestion.processing import DocumentProcessor
from knora.providers.embedding import EmbeddingConfiguration
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
    providers = build_provider_selection(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        del application
        try:
            yield
        finally:
            close_embedding = getattr(providers.embedding_provider, "close", None)
            if close_embedding is not None:
                close_embedding()
            close_generation = getattr(providers.generation_provider, "aclose", None)
            if close_generation is not None:
                await close_generation()

    application = FastAPI(title="Knora Agent", version="0.1.0", lifespan=lifespan)
    selected_embedding_configuration = embedding_configuration or providers.embedding_configuration
    answering_store = PostgresAnsweringStore(SessionFactory)
    workspace_admissions = (
        PostgresWorkspaceAdmissionStore(SessionFactory)
        if workspace_admission_store is _DEFAULT_WORKSPACE_ADMISSIONS
        else workspace_admission_store
    )
    application.state.workspace_admission_store = workspace_admissions
    application.state.answer_question = answer_question or AnswerQuestion(
        embedding_provider=providers.embedding_provider,
        generation_provider=providers.generation_provider,
        store=answering_store,
        embedding_configuration=selected_embedding_configuration,
        retrieval_configuration_resolver=DeploymentRetrievalConfigurationResolver(
            resolve_retrieval_configuration(
                settings.retrieval_configuration_id,
                vector_min_similarity=settings.vector_min_similarity,
            )
        ),
        admission_store=workspace_admissions,
    )
    application.state.ingest_document = ingest_document or IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=providers.embedding_provider,
        store=PostgresIngestionStore(SessionFactory),
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
    job_store = PostgresIngestionJobStore(SessionFactory)
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
    application.state.ingestion_worker = ingestion_worker or ProcessIngestionJob(
        store=job_store,
        handler=PdfDerivationHandler(
            object_store=selected_object_store,
            extractor=PypdfTextExtractor(),
            embedding_provider=providers.embedding_provider,
            profile_resolver=job_store.pdf_profile_for_work,
            runtime_embedding_configuration=selected_embedding_configuration,
        ),
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
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
    operator_reader = PostgresOperatorReader(SessionFactory)
    application.state.operator_observability = operator_observability or OperatorObservability(
        trace_reader=operator_reader,
        evaluation_reader=operator_reader,
        operations_reader=selected_metrics_store,
    )
    application.state.api_key_authenticator = api_key_authenticator or ApiKeyAuthenticator(
        credentials_from_json(settings.api_credentials_json)
    )
    selected_document_reader = document_reader or PostgresDocumentReader(SessionFactory)
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
            "INVALID_CONVERSATION_TITLE": 422,
            "INVALID_CONVERSATION_CURSOR": 422,
            "INVALID_CONVERSATION_LIMIT": 422,
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
            "PROVIDER_REQUEST_FAILED": 502,
            "PROVIDER_RESPONSE_INVALID": 502,
            "PERSISTENCE_OPERATION_FAILED": 500,
            "INVALID_IDEMPOTENCY_KEY": 400,
            "MISSING_IDEMPOTENCY_KEY": 400,
            "INVALID_PDF_SIGNATURE": 400,
            "PDF_STREAM_NOT_SEEKABLE": 400,
            "OBJECT_STORE_METADATA_INVALID": 500,
            "OBJECT_NOT_FOUND": 404,
            "PDF_RESOURCE_LIMIT_EXCEEDED": 413,
            "PDF_INGESTION_NOT_CONFIGURED": 503,
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
