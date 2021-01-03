import os
import aiohttp

def version_format(year, month, day):
    d = "{0:0=2d}".format(int(day))  # d is the day as an int
    m = "{0:0=2d}".format(int(month))  # m is the month as an int
    y = "{0:0=2d}".format((int(year) - 2020) * 2 + 1 + int(m[0]))  # y is the year as an int
    return f"v{y}.{m[1]}.{d[0]}.{d[1]}"


def check_dir(fdir, sub_path=""):
    all_files = []
    for file in os.listdir(fdir):
        if os.path.isdir(os.path.join(fdir, file)):
            all_files.extend(check_dir(os.path.join(fdir, file), sub_path + f"{file}/"))
        if file.endswith(".py"):
            all_files.append(sub_path + file)
    return all_files


async def get_versions(fdir):
    version_result = {}
    files = check_dir(fdir)
    for f in files:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/repos/markbeep/Lecturfier/commits?path={f}") as r:
                result = await r.json()
        try:
            date = result[0]["commit"]["author"]["date"].split("T")[0].split("-")
            version_result[f.split("/")[-1]] = ({"path": f, "version": version_format(date[0], date[1], date[2]), "status": True})
        except IndexError:
            version_result[f.split("/")[-1]] = ({"path": f, "version": "FileNotFound", "status": False})
        except KeyError:
            version_result[f.split("/")[-1]] = ({"path": f, "version": "APILimit", "status": False})
            print("Currently being API rate-limited")
            break
    return version_result
