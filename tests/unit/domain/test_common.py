import pytest
from pydantic import ValidationError

from leogent.domain.common import GenerationParameters, Usage


def test_usage_totals_input_and_output_tokens() -> None:
    usage = Usage(input_tokens=12, output_tokens=4)

    assert usage.total_tokens == 16


def test_usage_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        Usage(input_tokens=-1, output_tokens=4)


def test_generation_parameters_reject_temperature_above_two() -> None:
    with pytest.raises(ValidationError):
        GenerationParameters(temperature=2.1)


def test_generation_parameters_have_stable_defaults() -> None:
    parameters = GenerationParameters()

    assert parameters.temperature == 0.7
    assert parameters.top_p == 1.0
    assert parameters.max_output_tokens == 4096
    assert parameters.stop == ()
