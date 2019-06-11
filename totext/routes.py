from flask import render_template, session
from totext import app
from totext.forms import QueryForm
from datetime import datetime
import requests
import urllib

PRODUCTION_URL = "https://prod.adsabs.harvard.edu/"
DEVELOPMENT_URL = "https://dev.adsabs.harvard.edu/"
ADS_URL = DEVELOPMENT_URL
API_URL = ADS_URL+"v1/"
BOOTSTRAP_SERVICE = API_URL+"accounts/bootstrap"
SEARCH_SERVICE = API_URL+"search/query"
API_TIMEOUT = 30

def is_expired(auth):
    expire_in = datetime.strptime(auth['expire_in'], "%Y-%m-%dT%H:%M:%S.%f")
    delta = expire_in - datetime.now()
    return delta.seconds < 0

@app.before_request
def before_request():
    """
    Store API anonymous cookie in session or if it exists, check if it has expired
    """
    if 'cookies' not in session:
        session['cookies'] = {}
    if 'auth' not in session or is_expired(session['auth']):
        # Example of session['auth'] content:
        #   {'username': 'anonymous@ads', 'scopes': ['execute-query', 'store-query'],
        #   'client_id': 'DpRqNMLSv9Rqjycpz1XTzLH8ZZunQ4KY5ynagmEg', 'access_token': '7vIASALjYla1ddaFD6A258bH1KfyPiKQ7l5RBSi2',
        #   'client_name': 'BB client', 'token_type': 'Bearer', 'ratelimit': 1.0, 'anonymous': True,
        #   'client_secret': '2yvOxfgZtBaiNzAGt2YYYhMKyhTxIFxS62rFtcxNdjEDqWu0w33vQhp41RaQ',
        #   'expire_in': '2019-06-12T14:15:17.823482', 'refresh_token': 'itRUeo3vshekgyMYNMDxoGb84C6NTYoqjQ156xO9'}
        r = requests.get(BOOTSTRAP_SERVICE, cookies=session['cookies'], timeout=API_TIMEOUT)
        r.raise_for_status()
        r.cookies.clear_expired_cookies()
        session['cookies'].update(r.cookies.get_dict())
        session['auth'] = r.json()

def abstract(bibcode):
    """
    Retrieve abstract
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    params = urllib.urlencode({
            'fl': 'title,bibcode,author,keyword,pub,aff,volume,year,[citations],property,pubdate,abstract,esources,data',
            'q': 'citations(bibcode:{0})'.format(bibcode),
            'rows': '25',
            'sort': 'date desc',
            'start': '0'
            })
    r = requests.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

def search(q, sort="date desc, bibcode desc"):
    """
    Execute query
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    params = urllib.urlencode({
                    'fl': 'title,abstract,comment,bibcode,author,keyword,id,citation_count,[citations],pub,aff,volume,pubdate,doi,pub_raw,page,links_data,property,esources,data,email,doctype',
                    'q': '{0}'.format(q),
                    'rows': '25',
                    'sort': '{0}'.format(sort),
                    'start': '0'
                })
    r = requests.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

@app.route('/', methods=['GET', 'POST'])
def index():
    form = QueryForm()
    if form.validate_on_submit():
        results = search(form.query.data)
        results = process_search_results(results)
        return render_template('index.html', title='Totext home', auth=session['auth'], form=QueryForm(), results=results['response'])
    return render_template('index.html', title='Totext home', auth=session['auth'], form=QueryForm())
    #return "Hello, World!"

    
def process_search_results(results):
    """reformat raw solr response before converting to html"""
    author_limit = 3
    for d in results['response']['docs']:
        if len(d['author']) > author_limit:
            msg = ' and {} more'.format(len(d['author']) - author_limit)
            d['author'] = d['author'][:author_limit]
            d['author'].append(msg)
    return results
