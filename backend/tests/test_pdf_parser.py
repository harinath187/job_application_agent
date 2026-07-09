import agents.pdf_parser as pdf_parser


def test_name_extraction_ignores_watermark_and_finds_sections_from_text():
    resume_text = """Cisco Confidential
Cisco Confidential
Cisco Confidential

K V H Reddy
kvhreddy47@gmail.com
+1 555 123 4567

Experience
Senior Software Engineer, Cisco
2020-Present
- Led backend services and CI/CD pipelines

Education
University of Hyderabad
B.Tech in Computer Science
2016-2020
"""

    name = pdf_parser._extract_name_from_resume_text(resume_text, email="kvhreddy47@gmail.com")
    sections = pdf_parser._extract_resume_sections_from_text(resume_text, email="kvhreddy47@gmail.com")

    assert name != "Cisco Confidential"
    assert name == "K V H Reddy"
    assert len(sections["experience"]) == 1
    assert sections["experience"][0]["company"] == "Cisco"
    assert len(sections["education"]) == 1
    assert sections["education"][0]["institution"] == "University of Hyderabad"


def test_section_detection_keeps_unpredictable_sections_separate():
    resume_text = """Maya Patel
maya@example.com

HOBBIES:
- Trail running
- Ceramic art

Awards
- Dean's List

PUBLICATIONS
- A Study on Resume Parsing

Volunteer Experience:
- Local food bank organizer
"""

    sections = pdf_parser._extract_resume_sections_from_text(resume_text, email="maya@example.com")

    assert sections["contact_info"]["name"] == "Maya Patel"
    assert sections["additional_sections"] == [
        {"heading": "HOBBIES", "items": ["Trail running", "Ceramic art"]},
        {"heading": "Awards", "items": ["Dean's List"]},
        {"heading": "PUBLICATIONS", "items": ["A Study on Resume Parsing"]},
        {"heading": "Volunteer Experience", "items": ["Local food bank organizer"]},
    ]
    assert sections["education"] == []
    assert sections["experience"] == []


def test_multi_line_education_entry_is_structured_as_one_object():
    resume_text = """Jordan Lee
jordan@example.com

Education
Bachelor of Technology in Computer Science
National Institute of Technology, Trichy
Trichy, TN
2017 - 2021
CGPA: 8.9/10
Relevant Coursework: Algorithms, Databases
"""

    sections = pdf_parser._extract_resume_sections_from_text(resume_text, email="jordan@example.com")

    assert len(sections["education"]) == 1
    education = sections["education"][0]
    assert education["degree"] == "Bachelor of Technology in Computer Science"
    assert education["institution"] == "National Institute of Technology, Trichy"
    assert education["location"] == "Trichy, TN"
    assert education["dates"] == "2017 - 2021"
    assert education["grade"] == "8.9/10"
    assert "Relevant Coursework: Algorithms, Databases" in education["details"]


def test_resume_extraction_prompt_builds_without_nameerror():
    prompt = pdf_parser._build_resume_extraction_prompt("Sample resume text")

    assert isinstance(prompt, str)
    assert "{heading: string, items: string[]}" in prompt
    assert "Sample resume text" in prompt
