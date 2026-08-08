"""Fixed retrieve-and-answer workflow with structured claims and citation validation."""

import json
import re
import time
from importlib.resources import files

from fedresearch.llm.client import ClaudeGenerator, Generator
from fedresearch.retrieval.service import RetrievalService
from fedresearch.schemas import Answer, GeneratedAnswer
from fedresearch.util import digest


def validate_citations(generated: GeneratedAnswer, evidence):
    """Helper to answer_question: reject unknown citations, uncited claims and inconsistent sufficiency."""
    identifiers = {e.evidence_id for e in evidence}
    if generated.sufficiency == "insufficient" and generated.claims:
        raise ValueError("An insufficient answer must not contain unsupported claims")
    if generated.sufficiency != "insufficient" and not generated.claims:
        raise ValueError("A sufficient/partial answer must contain cited claims")
    for claim in generated.claims:
        if not claim.text.strip() or not claim.citations or not set(claim.citations) <= identifiers:
            raise ValueError("Generated claim has missing or unknown citation IDs")
        if re.search(r"\[E\d+\]", claim.text):
            raise ValueError("Citation markers must be in the structured citation list")
    if generated.sufficiency != "sufficient" and not generated.limitations.strip():
        raise ValueError("A partial/insufficient answer must explain its evidence limitation")


def answer_question(
    service: RetrievalService, question: str, generator: Generator | None = None, **filters
) -> Answer:
    """Retrieve evidence, generate cited claims, validate citation IDs and record the answer trace."""
    started = time.perf_counter()
    evidence = service.retrieve(question, **filters)
    instructions = files("fedresearch").joinpath("llm/prompts/answer.md").read_text()
    usage = {}
    if not evidence:
        generated = GeneratedAnswer(
            sufficiency="insufficient",
            claims=[],
            limitations="No evidence fits the requested scope and evidence budget in the indexed corpus.",
        )
    else:
        generator = generator or ClaudeGenerator(service.settings)
        payload = json.dumps(
            {
                "question": question,
                "evidence": [
                    {
                        "id": e.evidence_id,
                        "paper": e.title,
                        "sections": e.section_paths,
                        "pdf_pages": e.pages,
                        "text": e.text,
                    }
                    for e in evidence
                ],
            },
            ensure_ascii=False,
        )
        generated = generator.generate(instructions, payload)
        usage = generator.usage
    validate_citations(generated, evidence)
    used = {identifier for claim in generated.claims for identifier in claim.citations}
    citations = {e.evidence_id: e for e in evidence if e.evidence_id in used}
    lines = [
        claim.text
        + " "
        + " ".join(f"[{identifier}]" for identifier in dict.fromkeys(claim.citations))
        for claim in generated.claims
    ]
    if generated.limitations:
        lines.append(generated.limitations)
    return Answer(
        question=question,
        answer_text="\n\n".join(lines),
        sufficiency=generated.sufficiency,
        claims=generated.claims,
        citations=citations,
        evidence=evidence,
        usage={
            "embedding": service.last_trace["embedding_usage"],
            "generation": usage,
            "reranking": {
                key: value
                for key, value in service.last_trace["reranking"].items()
                if key in {"input_tokens", "requests", "estimated_cost_usd"}
            },
        },
        trace={
            "retrieval": service.last_trace,
            "settings_hash": digest(service.settings.model_dump(mode="json")),
            "generation": service.settings.generation.model_dump(),
            "prompt_sha256": digest(instructions),
            "seconds": time.perf_counter() - started,
            "citation_validation": "IDs and original source provenance validated; semantic claim support requires review",
        },
    )
