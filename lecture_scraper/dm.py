from lecture_scraper.helpers import find_edit_events, new_event, edit_event, other_event, check_wrapper, get_wrapper
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin

def dm_check(url: str, online_soup: bs, local_soup: bs):
    """
    compares online_soup to local_soup
    specifically for DiscMath website
    """
    # LECTURES
    sel_path_lec = "#lecture > table > tbody > tr"

    def decode_lec(tr):
        tds = tr.select("td")
        a = tr.select_one("a")
        link = {"text": "Video: "+ a.text.strip(), "url": urljoin(url, a.attrs["href"])} if a else None
        return {
            "date": tds[0].text.strip(),
            "name": tds[1].text.strip(),
            "links": [link] if link else []
        }

    events = check_wrapper(online_soup, local_soup, sel_path_lec, decode_lec, "lecture")

    # EXERCISES
    sel_path_ex = "#exercise > table.headercol > tbody > tr"
    def decode_ex(tr):
        tds = tr.select("td")
        links = []
        for a in tds[3].select("a")+tds[4].select("a"):
            links.append({
                "text": a.text.strip(),
                "url": urljoin(url, a.attrs["href"])
            })
        return {
            "date": tds[1].text.strip(),
            "abgabe_date": tds[2].text.strip(),
            "name": tds[3].text.strip(),
            "links": links
        }

    events += check_wrapper(online_soup, local_soup, sel_path_ex, decode_ex, "exercise")

    return events if events else [other_event()]
