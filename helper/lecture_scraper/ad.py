from urllib.parse import urljoin

from bs4 import BeautifulSoup as bs

from helper.lecture_scraper.helpers import check_wrapper, other_event


def ad_check(url: str, online_soup: bs, local_soup: bs):
    """
    compares online_soup to local_soup
    specifically for A&D website
    """
    sel_path_lec = "#vorlesung > tr"

    def decode_lec(tr):
        tds = tr.select("td")
        name = tds[1].select_one("em").text.strip().strip(".") + ": "
        name += ", ".join([li.text for li in tds[1].select("li")])
        links = [{
                "url": urljoin(url, a.attrs["href"]),
                "text": a.text.strip()
            } for a in tds[2].select("a")]
        return {
            "date": tds[0].text.strip(),
            "name": name,
            "links": links
        }

    events = check_wrapper(online_soup, local_soup, sel_path_lec, decode_lec, "lecture")

    # EXERCISES
    sel_path_ex = "#uebungen > tr"
    def decode_ex(tr):
        tds = tr.select("td")
        links = []
        for a in tr.select("a"):
            links.append({
                "text": a.text.strip(),
                "url": urljoin(url, a.attrs["href"])
            })
        return {
            "date": "unknown",
            "abgabe_date": "unknown",
            "name": tds[0].text.strip(),
            "links": links
        }

    events += check_wrapper(online_soup, local_soup, sel_path_ex, decode_ex, "exercise")

    return events if events else [other_event()]
