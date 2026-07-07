import httpx
import pytest
import respx

from app.organism_fallback import AzureVisionOrganismFallback, OrganismFallbackUnavailable


@respx.mock
@pytest.mark.asyncio
async def test_azure_vision_fallback_maps_dog_to_display_suggestions() -> None:
    route = respx.post("https://vision.example/computervision/imageanalysis:analyze").mock(
        return_value=httpx.Response(
            200,
            json={
                "tagsResult": {
                    "values": [
                        {"name": "dog", "confidence": 0.94},
                        {"name": "indoor", "confidence": 0.89},
                    ]
                },
                "objectsResult": {"values": []},
            },
        )
    )
    fallback = AzureVisionOrganismFallback(
        endpoint="https://vision.example/",
        key="fake-key",
        timeout=5,
        min_confidence=0.55,
    )

    suggestions = await fallback.suggest(image_bytes=b"dog-jpeg", top_k=3)

    assert route.called
    assert route.calls[0].request.url.params["features"] == "tags,objects"
    assert route.calls[0].request.headers["Ocp-Apim-Subscription-Key"] == "fake-key"
    assert [(s.common_name, s.scientific_name, s.score) for s in suggestions] == [
        ("Dog", "Canis familiaris", 94.0),
        ("Mammal", None, 86.5),
        ("Animal", None, 86.5),
    ]


@respx.mock
@pytest.mark.asyncio
async def test_azure_vision_fallback_ignores_person_and_non_organism_labels() -> None:
    respx.post("https://vision.example/computervision/imageanalysis:analyze").mock(
        return_value=httpx.Response(
            200,
            json={
                "tagsResult": {
                    "values": [
                        {"name": "person", "confidence": 0.97},
                        {"name": "indoor", "confidence": 0.92},
                        {"name": "furniture", "confidence": 0.87},
                    ]
                }
            },
        )
    )
    fallback = AzureVisionOrganismFallback(
        endpoint="https://vision.example",
        key="fake-key",
        timeout=5,
        min_confidence=0.55,
    )

    assert await fallback.suggest(image_bytes=b"room-jpeg", top_k=3) == []


@respx.mock
@pytest.mark.asyncio
async def test_azure_vision_fallback_raises_when_auth_fails() -> None:
    respx.post("https://vision.example/computervision/imageanalysis:analyze").mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    fallback = AzureVisionOrganismFallback(
        endpoint="https://vision.example",
        key="bad-key",
        timeout=5,
        min_confidence=0.55,
    )

    with pytest.raises(OrganismFallbackUnavailable):
        await fallback.suggest(image_bytes=b"dog-jpeg", top_k=3)
