from __future__ import annotations

from src.core.types import DocumentContext, Segment, SegmentBundle
from src.infra.config import TranslatorConfig


class Orchestrator:
    def build_bundles(self, segments: list[Segment], context: DocumentContext, config: TranslatorConfig) -> list[SegmentBundle]:
        bundles: list[SegmentBundle] = []
        current: list[Segment] = []
        current_chars = 0

        def flush() -> None:
            nonlocal current_chars
            if not current:
                return
            bundles.append(
                SegmentBundle(
                    bundle_id=f"bundle-{len(bundles)}",
                    segments=list(current),
                    summary_before=bundles[-1].summary_after if bundles else context.abstract[:200],
                    summary_after=self._build_bundle_summary(current),
                    glossary_terms=context.glossary,
                    style_instructions=context.style_guide,
                )
            )
            current.clear()
            current_chars = 0

        for segment in segments:
            segment_size = len(segment.source_text)
            if current and (
                len(current) >= config.segmentation.max_bundle_segments
                or current_chars + segment_size > config.segmentation.max_bundle_chars
            ):
                flush()
            current.append(segment)
            current_chars += segment_size
        flush()
        return bundles

    @staticmethod
    def _build_bundle_summary(segments: list[Segment]) -> str:
        text = " ".join(segment.source_text.replace("\n", " ") for segment in segments)
        return text[:240]
