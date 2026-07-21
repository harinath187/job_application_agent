def test_compute_skill_overlap_exact_match():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap(["Python", "SQL", "AWS"], ["Python", "SQL"])

    assert result.overlap_score == 1.0
    assert result.matched_skills == ["Python", "SQL"]
    assert result.missing_skills == []


def test_compute_skill_overlap_synonym_match():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap(["JavaScript", "Machine Learning"], ["JS", "ML"])

    assert result.overlap_score == 1.0
    assert result.matched_skills == ["JS", "ML"]
    assert result.missing_skills == []


def test_compute_skill_overlap_fuzzy_near_match():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap(["Kubernetes"], ["Kubernetees"])

    assert result.overlap_score == 1.0
    assert result.matched_skills == ["Kubernetees"]


def test_compute_skill_overlap_no_overlap():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap(["Python", "SQL"], ["Rust", "Go"])

    assert result.overlap_score == 0.0
    assert result.matched_skills == []
    assert result.missing_skills == ["Rust", "Go"]


def test_compute_skill_overlap_empty_resume_skills():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap([], ["Python", "SQL"])

    assert result.overlap_score == 0.0
    assert result.matched_skills == []
    assert result.missing_skills == ["Python", "SQL"]


def test_compute_skill_overlap_empty_job_skills():
    from backend.agents.skill_extractor import compute_skill_overlap

    result = compute_skill_overlap(["Python", "SQL"], [])

    assert result.overlap_score == 0.0
    assert result.matched_skills == []
    assert result.missing_skills == []


def test_extract_required_skills_uses_keyword_fallback_without_api_key(monkeypatch):
    from backend.agents import skill_extractor

    monkeypatch.setattr(skill_extractor, "GROQ_API_KEY", None)
    skill_extractor._SKILL_EXTRACTION_CACHE.clear()

    skills = skill_extractor.extract_required_skills(
        "We need a Python developer experienced with AWS, Docker, and SQL.",
        job_id="job-fallback-1",
    )

    assert "Python" in skills
    assert "AWS" in skills
    assert "SQL" in skills


def test_extract_required_skills_caches_per_job_id(monkeypatch):
    from backend.agents import skill_extractor

    monkeypatch.setattr(skill_extractor, "GROQ_API_KEY", None)
    skill_extractor._SKILL_EXTRACTION_CACHE.clear()

    call_count = {"n": 0}
    original = skill_extractor._heuristic_extract_skills

    def counting_fallback(description):
        call_count["n"] += 1
        return original(description)

    monkeypatch.setattr(skill_extractor, "_heuristic_extract_skills", counting_fallback)

    skill_extractor.extract_required_skills("Python and SQL required.", job_id="job-cache-1")
    skill_extractor.extract_required_skills("Python and SQL required.", job_id="job-cache-1")

    assert call_count["n"] == 1
