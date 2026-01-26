#!/usr/bin/env python3

import argparse
import requests
import datetime
from fpdf import FPDF
import os
import re
from sympy.parsing.latex import parse_latex
from sympy import pretty

class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def fetch_repos(username, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    repos = []
    url = f"https://api.github.com/users/{username}/repos?type=public&per_page=100"
    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        repos.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return repos

def fetch_readme(username, repo_name, token=None):
    headers = {"Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.text
    return None

def fetch_contributions(username, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    query = f"""
    {{
      user(login: "{username}") {{
        contributionsCollection {{
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                contributionCount
                date
                color
              }}
            }}
          }}
        }}
      }}
    }}
    """
    resp = requests.post("https://api.github.com/graphql", headers=headers, json={"query": query})
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise ValueError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def latex_to_unicode(tex):
    try:
        expr = parse_latex(tex)
        return pretty(expr)
    except Exception:
        # Fallback to manual if parsing fails, ASCII safe
        symbols = {
            r'\alpha': 'a', r'\beta': 'b', r'\gamma': 'g', r'\delta': 'd',
            r'\epsilon': 'e', r'\zeta': 'z', r'\eta': 'n', r'\theta': 'th',
            r'\iota': 'i', r'\kappa': 'k', r'\lambda': 'l', r'\mu': 'm',
            r'\nu': 'v', r'\xi': 'x', r'\pi': 'p', r'\rho': 'r',
            r'\sigma': 's', r'\tau': 't', r'\upsilon': 'u', r'\phi': 'ph',
            r'\chi': 'ch', r'\psi': 'ps', r'\omega': 'o',
            r'\Gamma': 'G', r'\Delta': 'D', r'\Theta': 'Th', r'\Lambda': 'L',
            r'\Xi': 'X', r'\Pi': 'P', r'\Sigma': 'S', r'\Upsilon': 'U',
            r'\Phi': 'Ph', r'\Psi': 'Ps', r'\Omega': 'O',
            r'\infty': 'inf', r'\pm': '+/-', r'\mp': '-/+', r'\times': 'x',
            r'\div': '/', r'\leq': '<=', r'\geq': '>=', r'\neq': '!=',
            r'\approx': '~', r'\equiv': '==', r'\int': 'int', r'\sum': 'sum',
            r'\prod': 'prod', r'\sqrt': 'sqrt', r'\partial': 'd',
        }
        for k, v in symbols.items():
            tex = tex.replace(k, v)

        # Superscripts
        def to_sup(s):
            return '^' + s

        tex = re.sub(r'\^{([^{}]+)}', lambda m: to_sup(m.group(1)), tex)
        tex = re.sub(r'\^([a-zA-Z0-9])', lambda m: to_sup(m.group(1)), tex)

        # Subscripts
        def to_sub(s):
            return '_' + s

        tex = re.sub(r'_{([^{}]+)}', lambda m: to_sub(m.group(1)), tex)
        tex = re.sub(r'_([a-zA-Z0-9])', lambda m: to_sub(m.group(1)), tex)

        # Fractions
        tex = re.sub(r'\\frac{([^{}]+)}{([^{}]+)}', lambda m: m.group(1) + '/' + m.group(2), tex)

        return tex

def process_readme_line(pdf, line, in_code_block, in_inline_code):
    if line.strip().startswith('```'):
        return not in_code_block, False

    if in_code_block:
        pdf.set_font("courier", "", 9)
        pdf.multi_cell(0, 4, line)
        return in_code_block, in_inline_code

    stripped_line = line.lstrip()
    indent = len(line) - len(stripped_line)

    ul_match = re.match(r'([-*+])\s+(.*)', stripped_line)
    if ul_match:
        pdf.set_font("helvetica", "", 10)
        pdf.set_x(10 + indent * 2)
        pdf.cell(10, 5, '*', 0, 0)
        process_inline(pdf, ul_match.group(2))
        pdf.ln(5)
        return in_code_block, in_inline_code

    ol_match = re.match(r'(\d+)\.\s+(.*)', stripped_line)
    if ol_match:
        pdf.set_font("helvetica", "", 10)
        pdf.set_x(10 + indent * 2)
        pdf.cell(10, 5, ol_match.group(1) + '.', 0, 0)
        process_inline(pdf, ol_match.group(2))
        pdf.ln(5)
        return in_code_block, in_inline_code

    header_match = re.match(r'^(#{1,6})\s+(.*)', stripped_line)
    if header_match:
        level = len(header_match.group(1))
        size = max(16 - level * 2, 10)
        pdf.set_font("helvetica", "B", size)
        pdf.set_x(10 + indent * 2)
        pdf.multi_cell(0, size / 2 + 4, header_match.group(2))
        return in_code_block, in_inline_code

    pdf.set_x(10 + indent * 2)
    process_inline(pdf, stripped_line)
    pdf.ln(5)
    return in_code_block, in_inline_code

def process_inline(pdf, text):
    math_parts = re.split(r'\$([^$]+)\$', text)
    for m, mpart in enumerate(math_parts):
        if m % 2 == 1:
            math_text = latex_to_unicode(mpart)
            pdf.set_font("helvetica", "I", 10)
            pdf.multi_cell(0, 5, math_text)
            continue

        code_parts = re.split(r'`(?!`)([^`]+)`', mpart)
        for c, cpart in enumerate(code_parts):
            if c % 2 == 1:
                pdf.set_font("courier", "", 9)
                pdf.multi_cell(0, 5, cpart)
                continue

            bold_parts = re.split(r'\*\*(.*?)\*\*', cpart)
            for b, bpart in enumerate(bold_parts):
                if b % 2 == 1:
                    pdf.set_font("helvetica", "B", 10)
                else:
                    pdf.set_font("helvetica", "", 10)
                if bpart:
                    pdf.multi_cell(0, 5, bpart)

def generate_pdf(username, repos, contrib, prioritize, exclude, output):
    # Prepare sorted repos
    prio_repos = [r for r in repos if r["name"] in prioritize]
    prio_repos.sort(key=lambda r: prioritize.index(r["name"]))
    other_repos = [r for r in repos if r["name"] not in prioritize and r["name"] not in exclude]
    other_repos.sort(key=lambda r: r["stargazers_count"], reverse=True)
    sorted_repos = prio_repos + other_repos

    toc_entries = []
    if contrib:
        toc_entries.append("Contribution Calendar")
    for repo in sorted_repos:
        toc_entries.append(repo["name"])

    # Generate content and record relative pages
    content_pdf = PDF()
    content_pdf.add_page()
    rel_pages = []
    links = []  # Not used in content_pdf

    if contrib:
        rel_pages.append(content_pdf.page_no())
        content_pdf.set_font("helvetica", "B", 12)
        content_pdf.cell(0, 10, "Contribution Calendar", align="C")
        content_pdf.ln(15)  # Increased space to avoid overlap
        square_size = 3
        spacing = 0.5
        weeks = contrib["weeks"][1:]
        num_weeks = len(weeks)

        # Draw month labels above
        current_month = None
        start_x = 20
        calendar_y = content_pdf.get_y()
        for w, week in enumerate(weeks):
            month_x = start_x + w * (square_size + spacing)
            if week["contributionDays"]:
                first_day = week["contributionDays"][0]
                date = datetime.date.fromisoformat(first_day["date"])
                month = date.strftime("%b")
                if month != current_month:
                    content_pdf.set_font("helvetica", size=8)
                    content_pdf.text(month_x, calendar_y - 2, month)
                    current_month = month

        days = ["", "Mon", "", "Wed", "", "Fri", "" ]
        content_pdf.set_font("helvetica", size=8)
        for d in range(7):
            y = calendar_y + d * (square_size + spacing) + square_size / 2
            content_pdf.text(5, y, days[d])

        for w, week in enumerate(weeks):
            for d, day in enumerate(week["contributionDays"]):
                x = start_x + w * (square_size + spacing)
                y = calendar_y + d * (square_size + spacing)
                r, g, b = hex_to_rgb(day["color"])
                content_pdf.set_fill_color(r, g, b)
                content_pdf.rect(x, y, square_size, square_size, "F")
        content_pdf.set_y(calendar_y + 7 * (square_size + spacing) + 10)
        content_pdf.ln(10)

    for repo in sorted_repos:
        rel_pages.append(content_pdf.page_no())
        content_pdf.set_font("helvetica", "B", 14)
        content_pdf.cell(0, 10, repo["name"])
        content_pdf.ln(10)
        content_pdf.set_font("helvetica", "", 12)
        desc = repo["description"] or "No description"
        content_pdf.multi_cell(0, 10, desc)
        content_pdf.set_font("helvetica", "U", 12)
        content_pdf.set_text_color(0, 0, 255)
        content_pdf.cell(0, 10, repo["name"], link=repo["html_url"])
        content_pdf.ln(10)
        content_pdf.set_text_color(0, 0, 0)
        content_pdf.set_font("helvetica", "", 12)
        readme = fetch_readme(username, repo["name"])
        if readme:
            content_pdf.set_font("helvetica", "B", 12)
            content_pdf.cell(0, 10, "README:")
            content_pdf.ln(10)
            lines = readme.split('\n')
            in_code_block = False
            in_inline_code = False
            for line in lines:
                in_code_block, in_inline_code = process_readme_line(content_pdf, line, in_code_block, in_inline_code)
        content_pdf.ln(10)

    # Now iterate to find TOC pages
    assumed_toc_pages = 1
    while True:
        content_start = 1 + assumed_toc_pages
        abs_pages = [rel + content_start - 1 for rel in rel_pages]

        toc_pdf = PDF()
        toc_pdf.add_page()
        toc_pdf.set_font("helvetica", "B", 12)
        toc_pdf.cell(0, 10, "Table of Contents", align="C")
        toc_pdf.ln(10)
        toc_pdf.set_font("helvetica", "", 12)
        for i, entry in enumerate(toc_entries):
            w = toc_pdf.get_string_width(entry) + 6
            toc_pdf.cell(w, 5, entry)
            dot_w = 170 - w
            dots = '.' * (int(dot_w / toc_pdf.get_string_width('.')) - 1)
            toc_pdf.cell(dot_w, 5, dots)
            toc_pdf.cell(10, 5, str(abs_pages[i]), align='R')
            toc_pdf.ln(5)

        actual_toc_pages = toc_pdf.page_no()
        if actual_toc_pages == assumed_toc_pages:
            break
        assumed_toc_pages = actual_toc_pages

    # Now build final PDF
    final_pdf = PDF()
    # Title page
    final_pdf.add_page()
    final_pdf.set_font("helvetica", "B", 16)
    final_pdf.cell(0, 10, f"{username}'s GitHub Portfolio", align="C")

    # TOC pages
    final_pdf.add_page()
    links = []
    final_pdf.set_font("helvetica", "B", 12)
    final_pdf.cell(0, 10, "Table of Contents", align="C")
    final_pdf.ln(10)
    final_pdf.set_font("helvetica", "", 12)
    for i, entry in enumerate(toc_entries):
        link = final_pdf.add_link()
        links.append(link)
        w = final_pdf.get_string_width(entry) + 6
        final_pdf.cell(w, 5, entry, link=link)
        dot_w = 170 - w
        dots = '.' * (int(dot_w / final_pdf.get_string_width('.')) - 1)
        final_pdf.cell(dot_w, 5, dots)
        final_pdf.cell(10, 5, str(abs_pages[i]), align='R')
        final_pdf.ln(5)

    # Content
    final_pdf.add_page()
    idx = 0
    if contrib:
        section_page = final_pdf.page_no()
        final_pdf.set_link(links[idx], page=section_page)
        idx += 1
        final_pdf.set_font("helvetica", "B", 12)
        final_pdf.cell(0, 10, "Contribution Calendar", align="C")
        final_pdf.ln(15)  # Increased space to avoid overlap
        square_size = 3
        spacing = 0.5
        weeks = contrib["weeks"][1:]
        num_weeks = len(weeks)

        current_month = None
        start_x = 20
        calendar_y = final_pdf.get_y()
        for w, week in enumerate(weeks):
            month_x = start_x + w * (square_size + spacing)
            if week["contributionDays"]:
                first_day = week["contributionDays"][0]
                date = datetime.date.fromisoformat(first_day["date"])
                month = date.strftime("%b")
                if month != current_month:
                    final_pdf.set_font("helvetica", size=8)
                    final_pdf.text(month_x, calendar_y - 2, month)
                    current_month = month

        days = ["", "Mon", "", "Wed", "", "Fri", "" ]
        final_pdf.set_font("helvetica", size=8)
        for d in range(7):
            y = calendar_y + d * (square_size + spacing) + square_size / 2
            final_pdf.text(5, y, days[d])

        for w, week in enumerate(weeks):
            for d, day in enumerate(week["contributionDays"]):
                x = start_x + w * (square_size + spacing)
                y = calendar_y + d * (square_size + spacing)
                r, g, b = hex_to_rgb(day["color"])
                final_pdf.set_fill_color(r, g, b)
                final_pdf.rect(x, y, square_size, square_size, "F")
        final_pdf.set_y(calendar_y + 7 * (square_size + spacing) + 10)
        final_pdf.ln(10)

    for repo in sorted_repos:
        section_page = final_pdf.page_no()
        final_pdf.set_link(links[idx], page=section_page)
        idx += 1
        final_pdf.set_font("helvetica", "B", 14)
        final_pdf.cell(0, 10, repo["name"])
        final_pdf.ln(10)
        final_pdf.set_font("helvetica", "", 12)
        desc = repo["description"] or "No description"
        final_pdf.multi_cell(0, 10, desc)
        final_pdf.set_font("helvetica", "U", 12)
        final_pdf.set_text_color(0, 0, 255)
        final_pdf.cell(0, 10, repo["name"], link=repo["html_url"])
        final_pdf.ln(10)
        final_pdf.set_text_color(0, 0, 0)
        final_pdf.set_font("helvetica", "", 12)
        readme = fetch_readme(username, repo["name"])
        if readme:
            final_pdf.set_font("helvetica", "B", 12)
            final_pdf.cell(0, 10, "README:")
            final_pdf.ln(10)
            lines = readme.split('\n')
            in_code_block = False
            in_inline_code = False
            for line in lines:
                in_code_block, in_inline_code = process_readme_line(final_pdf, line, in_code_block, in_inline_code)
        final_pdf.ln(10)

    final_pdf.output(output)

def generate_html(username, repos, contrib, prioritize, exclude, output):
    with open(output, "w") as f:
        f.write("<html><head><title>{}'s GitHub Portfolio</title></head><body>\n".format(username))
        f.write("<h1>{}'s GitHub Portfolio</h1>\n".format(username))
        if contrib:
            f.write("<h2>Contribution Calendar</h2>\n")
            weeks = contrib["weeks"]
            num_weeks = len(weeks)
            f.write('<div style="display: grid; grid-template-columns: repeat({}, 10px); grid-auto-rows: 10px; gap: 2px;">\n'.format(num_weeks))
            for week in weeks:
                for day in week["contributionDays"]:
                    color = day["color"]
                    title = "{}: {} contributions".format(day["date"], day["contributionCount"])
                    f.write('<div style="background-color: {}; " title="{}"></div>\n'.format(color, title))
            f.write("</div>\n")

        prio_repos = [r for r in repos if r["name"] in prioritize]
        prio_repos.sort(key=lambda r: prioritize.index(r["name"]))
        other_repos = [r for r in repos if r["name"] not in prioritize and r["name"] not in exclude]
        other_repos.sort(key=lambda r: r["stargazers_count"], reverse=True)
        sorted_repos = prio_repos + other_repos

        for repo in sorted_repos:
            f.write("<h2>{}</h2>\n".format(repo["name"]))
            desc = repo["description"] or "No description"
            f.write("<p>{}</p>\n".format(desc))
            f.write('<a href="{}">Link</a>\n'.format(repo["html_url"]))
            readme = fetch_readme(username, repo["name"])
            if readme:
                f.write("<h3>README</h3>\n")
                f.write("<pre>{}</pre>\n".format(readme))
        f.write("</body></html>")

def generate_md(username, repos, contrib, prioritize, exclude, output):
    with open(output, "w") as f:
        f.write("# {}'s GitHub Portfolio\n\n".format(username))
        if contrib:
            f.write("## Contribution Calendar\n\n")
            f.write("Total contributions in the last year: {}\n\n".format(contrib["totalContributions"]))

        prio_repos = [r for r in repos if r["name"] in prioritize]
        prio_repos.sort(key=lambda r: prioritize.index(r["name"]))
        other_repos = [r for r in repos if r["name"] not in prioritize and r["name"] not in exclude]
        other_repos.sort(key=lambda r: r["stargazers_count"], reverse=True)
        sorted_repos = prio_repos + other_repos

        for repo in sorted_repos:
            f.write("## {}\n\n".format(repo["name"]))
            desc = repo["description"] or "No description"
            f.write("{}\n\n".format(desc))
            f.write("[Link]({})\n\n".format(repo["html_url"]))
            readme = fetch_readme(username, repo["name"])
            if readme:
                f.write("### README\n\n")
                f.write("{}\n\n".format(readme))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a GitHub portfolio in PDF, HTML, or Markdown.")
    parser.add_argument("username", help="GitHub username")
    parser.add_argument("--token", help="GitHub personal access token (optional, for higher rate limits)")
    parser.add_argument("--output", default="portfolio.pdf", help="Output file path")
    parser.add_argument("--format", choices=["pdf", "html", "md"], default="pdf", help="Output format")
    parser.add_argument("--no-calendar", action="store_true", help="Exclude the contribution calendar")
    parser.add_argument("--prioritize", nargs="*", default=[], help="List of repo names to prioritize at the top")
    parser.add_argument("--exclude", nargs="*", default=[], help="List of repo names to exclude")
    args = parser.parse_args()

    repos = fetch_repos(args.username, args.token)
    contrib = None if args.no_calendar else fetch_contributions(args.username, args.token)

    if args.format == "pdf":
        if not args.output.endswith(".pdf"):
            args.output += ".pdf"
        generate_pdf(args.username, repos, contrib, args.prioritize, args.exclude, args.output)
    elif args.format == "html":
        if not args.output.endswith(".html"):
            args.output += ".html"
        generate_html(args.username, repos, contrib, args.prioritize, args.exclude, args.output)
    elif args.format == "md":
        if not args.output.endswith(".md"):
            args.output += ".md"
        generate_md(args.username, repos, contrib, args.prioritize, args.exclude, args.output)

    print(f"Portfolio generated: {args.output}")