# 4_legal_to_article_relation.py
"""
법령용어 → 조문 연계 API (lstrmRltJo)
- MST = 법령용어 ID
- 연계법령(조문정보) 파싱
"""

import requests
import xml.etree.ElementTree as ET

OC = "turtle816"


def parse_related_law(node):
    """ <연계법령> 태그 파싱 """

    def text(tag):
        child = node.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    return {
        "연계법령id": node.attrib.get("id", ""),
        "법령명": text("법령명"),
        "조번호": text("조번호"),
        "조가지번호": text("조가지번호"),
        "조문내용": text("조문내용"),
        "용어구분코드": text("용어구분코드"),
        "용어구분": text("용어구분"),
        "조문연계용어링크": text("조문연계용어링크"),
    }


def fetch_legal_to_article(MST: str):
    """ 법령용어 ID(MST) → 관련 조문 목록 """
    url = (
        "https://www.law.go.kr/DRF/lawService.do"
        f"?OC={OC}&target=lstrmRltJo&type=XML&MST={MST}"
    )

    res = requests.get(url)
    res.raise_for_status()
    root = ET.fromstring(res.text)

    legal_node = root.find("법령용어")
    if legal_node is None:
        return {"법령용어id": MST, "법령용어명": "", "조문목록": []}

    legal_term_name = legal_node.findtext("법령용어명", "")

    articles = []
    for rel in legal_node.findall("연계법령"):
        articles.append(parse_related_law(rel))

    return {
        "법령용어id": MST,
        "법령용어명": legal_term_name,
        "조문목록": articles
    }


if __name__ == "__main__":
    example_MST = "1438791"  # 공제자산
    result = fetch_legal_to_article(example_MST)

    from pprint import pprint
    pprint(result)
