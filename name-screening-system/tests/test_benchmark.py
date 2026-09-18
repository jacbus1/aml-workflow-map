from scripts.run_public_benchmark import run


def test_public_people_benchmark_all_positive_and_negative_controls_pass():
    result = run(80)
    assert result["positive_passed"] == result["positive_total"]
    assert result["negative_passed"] == result["negative_total"]
