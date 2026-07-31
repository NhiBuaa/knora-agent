from fastapi import FastAPI

from knora.api.routes import router
from knora.application.answer_question import AnswerQuestion
from knora.domain.models import RetrievedChunk
from knora.providers.demo import DemoAnswerGenerator, DemoRetriever


def create_app() -> FastAPI:
    application = FastAPI(title="Knora Agent", version="0.1.0")
    demo_chunks = [
        RetrievedChunk(
            document_id="refund-policy",
            chunk_id="refund-policy:0",
            source="refund-policy.md",
            content="Khách hàng có thể yêu cầu hoàn tiền trong vòng 30 ngày kể từ ngày mua.",
            score=1.0,
        )
    ]
    application.state.answer_question = AnswerQuestion(
        retriever=DemoRetriever(demo_chunks),
        generator=DemoAnswerGenerator(),
    )
    application.include_router(router)
    return application


app = create_app()

