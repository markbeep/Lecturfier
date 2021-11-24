from urllib.parse import urljoin

from bs4 import BeautifulSoup as bs

from helper.lecture_scraper.helpers import (check_wrapper, find_edit_events,
                                            new_event, other_event)


def ep_check(url: str, online_soup: bs, local_soup: bs) -> bool:
    """
    compares online_soup to local_soup
    specifically for EProg website
    """
    # EXERCISES

    def decode_ex(tr) -> dict:
        tds = tr.select("td")
        links = []
        for a in tds[0].select("a") + tds[3].select("a"):
            # urls are absolute
            links.append({"text": a.text.strip(), "url": urljoin(url, a.attrs["href"])})

        return {
            "name": tds[0].text.strip(),
            "date": tds[1].text.strip(),
            "abgabe_date": tds[2].text.strip(),
            "links": links
        }
    
    events = check_wrapper(online_soup.select("table")[1], local_soup.select("table")[1], "tbody > tr", decode_ex, "exercise")

    # LECTURES

    # can't use check_wrapper() here, as one 
    # single entry is not in one html element.
    # aka; two lectures per table row
    html_now = online_soup.select("table")[0].select("tbody > tr")
    html_old = local_soup.select("table")[0].select("tbody > tr")

    def decode_lecs(trs):
        all_lecs = []
        for tr in trs:
            tds = tr.select("td")
            for part in [tds[:2], tds[2:]]: # to parts per tr
                links = [{
                    "url": urljoin(url, a.attrs["href"]), # don't join with url, as already absolute url
                    "text": a.text.strip()
                } for a in part[1].select("a")]
                all_lecs.append({
                    "date": part[0].text.strip(),
                    "name": part[1].text.strip(),
                    "links": links
                })
        return all_lecs

    lecs_now, lecs_old = decode_lecs(html_now), decode_lecs(html_old)

    events += find_edit_events(lecs_now, lecs_old, "lecture")
    # shouldn't have any new_events in eprog but doesn't harm to put it in
    events += [new_event(lec, "lecture") for lec in lecs_now[len(lecs_old):]]

    return events if events else [other_event()]
