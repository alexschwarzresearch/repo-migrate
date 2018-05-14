import configparser
import os
import json
import argparse

import requests
from pyld import jsonld

import constants

parser = argparse.ArgumentParser(description='List the contents of either repository or migrate the data from ckan to fedora.')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-l', '--list', type=str, choices={'ckan', 'fedora'})
group.add_argument('-m', '--migrate', action='store_true')

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'repo_migrate.config'))
CKAN_API = config['ckan']['CKAN_API']
FEDORA_API = config['fedora']['FEDORA_API']


def list_ckan():
    request_packages = requests.get(CKAN_API + 'action/package_list/')

    if request_packages.status_code > 400 or request_packages.json()['success'] is not True:
        print('The content of the ckan repository could not be displayed due to an error')
        return

    packages = request_packages.json()['result']

    if len(packages) == 0:
        print('The repository does not contain any collections.')
        return

    for package in packages:
        request_content = requests.get(CKAN_API + 'action/package_show?id=' + package)
        content = json.loads(request_content.text)['result']

        print_box(content['title'])
        print_exists(content, 'author')
        print_exists(content, 'maintainer')
        print_exists(content, 'notes', 'description')
        print_exists(content, 'license_id')

        print('file(s) [{}]:'.format(len(content['resources'])))
        for file in content['resources']:
            print('\t- ' + file['name'])
        print()


def list_fedora():
    request_organizations = requests.get(FEDORA_API, headers={'Accept': 'application/ld+json'})

    if request_organizations.status_code > 400:
        print('The content of the fedora repository could not be displayed due to an error')
        return

    organizations = jsonld.compact(request_organizations.json(), constants.CONTEXT_DICT)

    if 'ldp:contains' not in organizations:
        print('The repository does not contain any collections.')
        return

    # iterate over each organization
    if isinstance(organizations['ldp:contains'], list):
        for elem in organizations['ldp:contains']:
            print_fedora_organization_content(elem['@id'])
    else:
        print_fedora_organization_content(organizations['ldp:contains']['@id'])


def print_fedora_organization_content(organization_url):
    request_collections = requests.get(organization_url, headers={'Accept': 'application/ld+json'})
    collections = jsonld.compact(request_collections.json(), constants.CONTEXT_DICT)

    if 'ldp:contains' not in collections:
        print('The collection does not contain any content.')
        return

    # iterate over each collection
    if isinstance(collections['ldp:contains'], list):
        for elem in collections['ldp:contains']:
            print_fedora_collection(elem['@id'])
    else:
        print_fedora_collection(collections['ldp:contains']['@id'])


def print_fedora_collection(collection_url):
    request_collection = requests.get(collection_url, headers={'Accept': 'application/ld+json'})
    collection = jsonld.compact(request_collection.json(), constants.CONTEXT_DICT)

    print_box(collection['dc:title'])
    print_exists(collection, 'rm:author', 'author')
    print_exists(collection, 'rm:maintainer', 'maintainer')
    print_exists(collection, 'dc:description', 'description')
    print_exists(collection, 'premis:LicenseInformation', 'license_id')

    print('file(s) [{}]:'.format(len(collection['ldp:contains'])))

    if isinstance(collection['ldp:contains'], list):
        for elem in collection['ldp:contains']:
            file_url = elem['@id']
            metadata_url = file_url + '/fcr:metadata'

            print_fedora_file(metadata_url)
    else:
        print_fedora_file(collection['ldp:contains']['@id'] + '/fcr:metadata')

    print()


def print_fedora_file(file_metadata_url):
    request_metadata = requests.get(file_metadata_url, headers={'Accept': 'application/ld+json'})
    metadata = jsonld.compact(request_metadata.json(), constants.CONTEXT_DICT)
    print('\t- ' + metadata['ebucore:filename'])


def migrate():
    request_packages = requests.get(CKAN_API + 'action/package_list/')

    if request_packages.status_code > 400 or request_packages.json()['success'] is not True:
        print('Error while accessing ckan repository.')
        return

    packages = request_packages.json()['result']

    for package in packages:
        request_content = requests.get(CKAN_API + 'action/package_show?id=' + package)
        content = json.loads(request_content.text)['result']

        # organization

        organization_title = content['organization']['title']
        organization_description = content['organization']['title']
        create_organization(organization_title, organization_description)

        # collection information

        collection_url = FEDORA_API + organization_title + '/' + package + '/'
        collection_body = constants.CONTEXT_TEXT
        collection_body += get_ontology_string(content, 'license_id', 'premis:LicenseInformation')
        collection_body += get_ontology_string(content, 'license_title', 'rm:license_title')
        collection_body += get_ontology_string(content, 'license_url', 'rm:license_url')
        collection_body += get_ontology_string(content, 'title', 'dc:title')
        collection_body += get_ontology_string(content, 'maintainer', 'rm:maintainer')
        collection_body += get_ontology_string(content, 'maintainer_email', 'rm:maintainer_email')
        collection_body += get_ontology_string(content, 'num_tags', 'rm:num_tags')
        collection_body += get_ontology_string(content, 'author', 'rm:author')
        collection_body += get_ontology_string(content, 'author_email', 'rm:author_email')
        collection_body += get_ontology_string(content, 'num_resources', 'rm:num_resources')
        collection_body += get_ontology_string(content, 'notes', 'dc:description')

        # combine tags to single string
        if content['num_tags'] > 0:
            combined_tags = ''
            first = True
            for tag in content['tags']:
                if first:
                    combined_tags += tag['display_name']
                    first = False
                else:
                    combined_tags += ', ' + tag['display_name']
            collection_body += to_ontology_string('rm:tags', combined_tags)

        create_fedora_resource(collection_url, collection_body)

        for resource in content['resources']:
            file = requests.get(resource['url']).content
            resource_url = collection_url + resource['id']
            requests.put(
                url=resource_url,
                headers={'Content-Disposition': 'attachment; filename="{}"'.format(resource['name']),
                         'Content-Type': resource['mimetype']},
                data=file
            )

            # add resource attributes
            resource_body = constants.CONTEXT_TEXT
            resource_body += 'Insert {'
            resource_body += get_ontology_string(resource, 'description', 'dc:description')
            resource_body += get_ontology_string(resource, 'format', 'premis:Format')
            resource_body += get_ontology_string(resource, 'identifier', 'premis:Identifier')
            resource_body += get_ontology_string(resource, 'position', 'rm:position')
            resource_body += get_ontology_string(resource, 'bitrate', 'rm:bitrate')
            resource_body += get_ontology_string(resource, 'length', 'rm:length')
            resource_body += '} WHERE {}'

            requests.patch(
                url=resource_url + '/fcr:metadata',
                headers={'Content-Type': 'application/sparql-update'},
                data=resource_body
            )

    print('Finished migration.')


def create_organization(title, description):
    """
    creates a new organization at the first layer of fedora if it does not exist
    """

    url = FEDORA_API + title

    if requests.get(url).status_code == 200:
        # organization allready exists
        return

    create_fedora_resource(url, 'PREFIX dc: <http://purl.org/dc/elements/1.1/>\n<> dc:description "{}" .'.format(
        description))


def create_fedora_resource(url, body):
    """
    creates new fedora resource (overwrites old one if necessary)
    """
    remove_fedora_resoure(url)

    if body:
        requests.put(
            url=url,
            headers={'PREFER': 'handling=lenient; received="minimal"', 'Content-Type': 'text/turtle'},
            data=body
        )
    else:
        requests.put(url)


def remove_fedora_resoure(url):
    """
    removes the resource and the tombstone if they exist
    """
    requests.delete(url)
    requests.delete(url + '/fcr:tombstone')


def get_ontology_string(dict, key, predicate):
    if key not in dict or len(str(dict[key])) == 0:
        return ''

    return to_ontology_string(predicate, dict[key])


def to_ontology_string(predicate, value):
    return '<> {} "{}" .\n'.format(predicate, value)


def print_exists(dictionary, key, name=None):
    """
    prints key and value of dictionary entry if it exists and is not empty
    if name is given it replaces the name of the key in the output
    """
    if key not in dictionary or len(dictionary[key]) == 0:
        return

    if name:
        print(name + ': ' + dictionary[key])
    else:
        print(key + ': ' + dictionary[key])


def print_box(string):
    print('+' + '-' * len(string) + '+')
    print('|' + string + '|')
    print('+' + '-' * len(string) + '+')


def exit_with_error(message):
    print(message)
    exit(1)


if __name__ == '__main__':
    args = vars(parser.parse_args())
    if args['migrate']:
        migrate()
    elif args['list'] == 'ckan':
        list_ckan()
    else:
        list_fedora()
