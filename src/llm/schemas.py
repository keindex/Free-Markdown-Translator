TRANSLATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string"},
                    "translated_text": {"type": "string"},
                    "notes": {"type": "array", "items": {"type": "string"}},
                    "applied_terms": {"type": "object"},
                    "confidence": {"type": "number"},
                },
                "required": ["segment_id", "translated_text"],
            },
        }
    },
    "required": ["translations"],
}
