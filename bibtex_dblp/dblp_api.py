import logging
import re

import requests

import bibtex_dblp.config as config
import bibtex_dblp.dblp_data


def get_url_part(bib_format):
    """
    Get identifier of format for DBLP urls.
    :return:
    """
    assert bib_format in config.BIB_FORMATS
    if bib_format == config.CONDENSED:
        return "bib0"
    elif bib_format == config.STANDARD:
        return "bib1"
    elif bib_format == config.CROSSREF:
        return "bib2"


def extract_dblp_id(entry):
    """
    Extract DBLP id by either using the biburl if given or trying to use the entry name.
    :param entry: Bibliography entry.
    :return: DBLP id or None if no could be extracted.
    """
    if "biburl" in entry.fields:
        match = re.search(r"http(s?)://dblp.org/rec/(.*)", entry.fields["biburl"])
        if match:
            return match.group(2)

    t, k = sanitize_key(entry.key)
    if t == "DBLP":
        return k
    else:
        return None


def sanitize_key(k):
    """
    Given a key in one of these formats:
    DBLP:conf/spire/2006
    conf/spire/2006
    doi:10.1007/11880561
    10.1007/11880561
    Determine the key type and remove the type prefix if present.
    :param k: DBLP id or DOI for entry.
    :return: A tuple type, key.
    """
    if k[:5].upper() == "DBLP:":
        return "DBLP", k[5:]
    elif k[:4].upper() == "DOI:":
        return "DOI", k[4:]
    elif k.count("/") >= 2:
        logging.debug(f"Key {k} was *guessed* to be a DBLP id.")
        return "DBLP", k
    elif k.count("/") == 1:
        logging.debug(f"Key {k} was *guessed* to be a DOI.")
        return "DOI", k
    else:
        logging.error(f"Could not determine type of {k}.")
        return None, k


def bibtex_requests(type, key, bib_format, prefer_doi_org):
    part = get_url_part(bib_format)
    if type == "DBLP":
        url = config.DBLP_PUBLICATION_BIBTEX.format(key=key, bib_format=part)
        headers = None
        yield url, headers
    elif type == "DOI":
        url1 = config.DOI_FROM_DBLP.format(key=key, bib_format=part)
        headers1 = None
        url2 = config.DOI_FROM_DOI_ORG.format(key=key)
        headers2 = {"Accept": "application/x-bibtex; charset=utf-8"}
        if prefer_doi_org:
            yield url2, headers2
            yield url1, headers1
        else:
            yield url1, headers1
            yield url2, headers2


def get_bibtex(id, bib_format, prefer_doi_org=False):
    """
    Get bibtex entry in specified format.
    :param id: DBLP id or DOI for entry.
    :param bib_format: Format of bibtex export.
    :return: Bibtex as binary string.
    """
    assert bib_format in config.BIB_FORMATS
    t, k = sanitize_key(id)
    logging.debug(
        f"In get_bibtex({id}, {bib_format}): key has been sanitized to {t}, {k}"
    )
    for url, headers in bibtex_requests(t, k, bib_format, prefer_doi_org):
        if headers:
            resp = requests.get(url, headers=headers)
        else:
            resp = requests.get(url)
        if resp.status_code == 200:
            return resp.content.decode("utf-8")
        else:
            logging.warning(f"Could not retrieve {id} from {url}.")


def search_publication(pub_query, max_search_results):
    """
    Search for publication according to given query.
    :param pub_query: Query for publication.
    :param max_search_results: Maximal number of search results to return.
    :return: Search results.
    """
    parameters = dict(q=pub_query, format="json", h=max_search_results)

    resp = requests.get(config.DBLP_PUBLICATION_SEARCH_URL, params=parameters)
    assert resp.status_code == 200
    results = bibtex_dblp.dblp_data.DblpSearchResults(resp.json())
    assert results.status_code == 200
    return results
