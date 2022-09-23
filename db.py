import re
import helper.sql.SQLFunctions as sql

subjects = """Sem 1
===
Lineare Algebra (LA)
https://igl.ethz.ch/teaching/linear-algebra/la2022/
Mi 10.15 HG F 5
Fr 10.15 HG F 5

Diskrete Mathematik (DM)
https://crypto.ethz.ch/teaching/DM22/
Mo 14.15 ETA F 5
Mi 14.15 ETA F 5

Einführung in die Programmierung (EProg)
https://www.lst.inf.ethz.ch/education/einfuehrung-in-die-programmierung-i--252-0027-1.html
Di 10.15 ML D 28
Fr 8.15 ML D 28

Algorithmen und Datenstrukturen (AnD)
https://cadmo.ethz.ch/education/lectures/HS22/DA/index.html
Do 10.15 HG F 5
Do 14.15 ETA F 5


Sem 3
===
Theoretische Informatik (TI)
https://courses.ite.inf.ethz.ch/theo_inf_22/
Di 8.15 HG E 3
Fr 8.15 HG E 7

Systems Programming and Computer Architecture (SPCA)
https://systems.ethz.ch/education/courses/2022-autumn-semester/systems-programming-and-computer-architecture-.html
Di 10.15 HG E 7
Mi 10.15 NO C 60

Analysis II (Ana2)
https://metaphor.ethz.ch/x/2022/hs/401-0213-16L/
Do 14.15 HG E 7

Numerical Methods for Computer Science (NumCS)
https://moodle-app2.let.ethz.ch/course/view.php?id=17727
Do 10.15 HG F 1

Sem 5
===
Visual Computing (VC)
https://cvg.ethz.ch/teaching/visualcomputing/
Di 10.15 HG G 3
Do 14.15 HG G 3

Algorithms, Probability, and Computing (APC)
https://ti.inf.ethz.ch/ew/courses/APC22/
Mo 14.15 ML D 28
Do 14.15 ML D 28

Compiler Design (CD)
https://moodle-app2.let.ethz.ch/user/index.php?id=15894
Mi 14.15 HG E 3
Do 16.15 ETF E 1

Computer Systems (CS)
https://systems.ethz.ch/education/courses/2022-autumn-semester/computer-systems-.html
Mo 10.15 CAB G 61
Fr 10.15 CAB G 61"""


def times(text):
    t = re.compile("(Mo|Di|Mi|Do|Fr) (\d+)\.(\d+) (\w+) (\w+) (\d+)")
    res = t.findall(text)
    return res[0]


def handle(text):
    sub = []
    lines = [x for x in text.split("\n") if len(x) > 0]
    sub.append(lines[0])
    sub.append(lines[1])
    sub.append([times(lines[i]) for i in range(2, len(lines))])
    return sub


def exe():
    r = re.compile("Sem \d+\n===")
    semesters = r.split(subjects)
    data = {}
    semesters = [x for x in semesters if len(x) > 0]
    for i, sem in enumerate(semesters):
        data[i*2+1] = []
        subjs = sem.split("\n\n")
        for s in subjs:
            if len(s) < 5:
                continue
            data[i*2+1].append(handle(s))
    print(data)

    a = re.compile(r"(.+) \((\w+)\)")
    dayids = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    for sem in data.keys():
            for name, link, rooms in data[sem]:
                name, abbrev = a.findall(name)[0]
                for r in rooms:
                    stream_link = f"https://video.ethz.ch/live/lectures/zentrum/{r[3].lower()}/{r[3].lower()}-{r[4].lower()}-{r[5]}.html"
                    sql.update_or_insert_weekdaytime(
                        name,
                        abbrev,
                        link,
                        None,
                        stream_link,
                        f"{r[3]} {r[4]} {r[5]}",
                        sem,
                        r[1],
                        0,
                        dayids.index(r[0])
                    )
