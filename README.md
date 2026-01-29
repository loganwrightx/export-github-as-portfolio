# Export GitHub as Portfolio
A python tool to export your GitHub profile as either a PDF, HTML, or Markdown portfolio. The portfolio will only display public repositories and user has control over what parts are displayed.

## Simple Usage

1. Create a `.env` file with your GitHub personal access token (see GitHub docs to generate the PAT if you haven't yet)
2. After creating the `.env` file in this project's working directory, add the following line (replacing `<your-personal-access-token>` with your actual PAT): `GITHUB_PAT=<your-personal-access-token>`
3. Source your `.env` file using the following command: `source .env`
  - If you want the `GITHUB_PAT` environment variable to be persistent across all terminals, append the following line to your `.bashrc` or `.bash_profile` file in `~`: `export GITHUB_PAT=<your-personal-access-token>`
5. Run the a simple demo with the following command: `./export-github-as-portfolio.py <your-github-username> --output ./<your-github-username>.pdf --prioritize <your-favorite-public-project> --format pdf --token "$GITHUB_PAT"`

## Additional Usage Information

To see supported commands, run `./export-github-as-portfolio.py -h` or `./export-github-as-portfolio.py --help` to see:

```bash
usage: export-github-as-portfolio.py [-h] [--token TOKEN] [--output OUTPUT] [--format {pdf,html,md}] [--no-calendar] [--prioritize [PRIORITIZE ...]] [--exclude [EXCLUDE ...]]
                                     username

Generate a GitHub portfolio in PDF, HTML, or Markdown.

positional arguments:
  username              GitHub username

options:
  -h, --help            show this help message and exit
  --token TOKEN         GitHub personal access token (optional, for higher rate limits)
  --output OUTPUT       Output file path
  --format {pdf,html,md}
                        Output format
  --no-calendar         Exclude the contribution calendar
  --prioritize [PRIORITIZE ...]
                        List of repo names to prioritize at the top
  --exclude [EXCLUDE ...]
                        List of repo names to exclude
```