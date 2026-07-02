from tasks.classify import infer_page_kind, infer_source_scope


def test_infer_source_scope_classifies_known_source_ranges():
    assert (
        infer_source_scope(
            url="https://www.honam.ac.kr/General_Rest",
            site_url="https://www.honam.ac.kr",
        )
        == "general_academic"
    )
    assert (
        infer_source_scope(
            url="https://enter.honam.ac.kr/faq/1",
            site_url="https://enter.honam.ac.kr",
        )
        == "admission"
    )
    assert (
        infer_source_scope(
            url="https://com.honam.ac.kr/DepartmentNotice",
            site_url="https://com.honam.ac.kr",
        )
        == "department"
    )
    assert (
        infer_source_scope(
            url="https://www.honam.ac.kr/Schedule",
            site_url="https://www.honam.ac.kr",
        )
        == "general_academic"
    )
    assert (
        infer_source_scope(
            url="https://www.honam.ac.kr/Certificate",
            site_url="https://www.honam.ac.kr",
        )
        == "general_academic"
    )
    assert (
        infer_source_scope(
            url="https://www.honam.ac.kr/Contact",
            site_url="https://www.honam.ac.kr",
        )
        == "general_academic"
    )


def test_infer_page_kind_classifies_document_function_independently_from_source():
    assert (
        infer_page_kind(url="https://www.honam.ac.kr/General_Rest", menu_path="일반휴학")
        == "academic"
    )
    assert (
        infer_page_kind(url="https://enter.honam.ac.kr/faq/1", menu_path="입학 FAQ") == "admission"
    )
    assert (
        infer_page_kind(url="https://www.honam.ac.kr/Schedule", menu_path="학사일정") == "schedule"
    )
    assert (
        infer_page_kind(
            url="https://www.honam.ac.kr/SchbusGuideSchedule",
            menu_path="통학버스/교통편 안내",
        )
        == "academic"
    )
    assert (
        infer_page_kind(
            url="https://www.honam.ac.kr/SchbusLocation",
            menu_path="등교버스 위치조회",
        )
        == "academic"
    )
    assert (
        infer_page_kind(url="https://www.honam.ac.kr/Certificate", menu_path="증명서 발급")
        == "certificate"
    )
    assert (
        infer_page_kind(
            url="https://beauty.honam.ac.kr/FaceCertificate",
            menu_path="피부자격증취득반",
        )
        == "academic"
    )
    assert (
        infer_page_kind(url="https://www.honam.ac.kr/Contact", menu_path="부서별 연락처")
        == "contact"
    )
    assert (
        infer_page_kind(url="https://enter.honam.ac.kr/contact", menu_path="입학처 연락처")
        == "contact"
    )
    assert (
        infer_page_kind(url="https://www.honam.ac.kr/Directions", menu_path="찾아오시는 길")
        == "contact"
    )
    assert (
        infer_page_kind(
            url="https://www.honam.ac.kr/UnionCourseAYStand",
            menu_path="교직과정 입학년도 결정기준",
        )
        == "academic"
    )
    assert (
        infer_page_kind(
            url="https://english.honam.ac.kr/TeachingCourse",
            menu_path="교직과정(2021입학자까지)",
        )
        == "academic"
    )
    assert (
        infer_page_kind(url="https://com.honam.ac.kr/SiteMap", menu_path="사이트맵") == "academic"
    )
