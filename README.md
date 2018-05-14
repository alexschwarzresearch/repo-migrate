<h1 align="center">RepoMigrate</h1>

<p align="center">
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" />
  </a>
  <a href="https://orcid.org/0000-0001-5159-8864">
    <img src="https://img.shields.io/badge/ORCiD-0000--0001--5159--8864-brightgreen.svg"/>
  </a>
</p>

RepoMigrate lets you list the contents of your ckan and fedora repository and allows you to perform a migration from ckan to fedora.

## Author

Alexander Schwarz | [ORCiD](https://orcid.org/0000-0001-5159-8864)

## Technologies

 * Python 3.5

## Setup

1. install the required packages with: ``` $ pip install -r requirements.txt ```
2. customise the API endpoints of the repositories in the [repo_migrate.config](repo_migrate.config) file
3. run the program

## Usage

```
usage: repo_migrate.py [-h] (-l {fedora,ckan} | -m)

List the contents of either repository or migrate the data from ckan to
fedora.

optional arguments:
  -h, --help          show this help message and exit
  -l {fedora,ckan}, --list {fedora,ckan}
  -m, --migrate
```

## License

[MIT](LICENSE)