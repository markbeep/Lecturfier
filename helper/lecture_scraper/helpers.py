def find_edit_events(news: list, olds: list, type_name) -> dict:
    edited_events = []
    for new, old in zip(news, olds):
        if new != old: # print changes in all changed entries (i.e. new solutions)
            edited_keys = []
            for key in new:
                if new[key] != old[key]:
                    edited_keys.append(key)
            edited_events.append(edit_event(new, old, edited_keys, type_name))

    return edited_events

def check_wrapper(online_soup, local_soup, sel_path, decode_html_fn, type_name):
    # select html tags from soup
    html_now = online_soup.select(sel_path)
    html_old = local_soup.select(sel_path)
    # decode them into dicts
    dicts_now = [decode_html_fn(x) for x in html_now]
    dicts_old = [decode_html_fn(x) for x in html_old]

    edits = find_edit_events(dicts_now, dicts_old, type_name)
    news = [new_event(lec, type_name) for lec in dicts_now[len(dicts_old):]]
    return edits + news

def get_wrapper(online_soup, local_soup, sel_path, decode_html_fn, type_name):
    # select html tags from soup
    html_now = online_soup.select(sel_path)
    html_old = local_soup.select(sel_path)
    # decode them into dicts
    dicts_now = [decode_html_fn(x) for x in html_now]
    dicts_old = [decode_html_fn(x) for x in html_old]

    return {"now": dicts_now, "old": dicts_old}

def edit_event(new, old, edited_keys, type_):
    return {
        "event": "edit",
        "type": type_,
        "content": {
            "new": new,
            "old": old,
            "keys": edited_keys
        }
    }

def new_event(new_entry, type_):
    return {
        "event": "new",
        "type": type_,
        "content": new_entry
    }
def other_event():
    return {
        "event": "other"
    }