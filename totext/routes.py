from flask import render_template, session, request, redirect, g
from totext import app
from totext.forms import QueryForm
from datetime import datetime
import requests
import urllib
import time

PRODUCTION_URL = "https://prod.adsabs.harvard.edu/"
DEVELOPMENT_URL = "https://dev.adsabs.harvard.edu/"
ADS_URL = DEVELOPMENT_URL
API_URL = ADS_URL+"v1/"
BOOTSTRAP_SERVICE = API_URL+"accounts/bootstrap"
SEARCH_SERVICE = API_URL+"search/query"
EXPORT_SERVICE = API_URL+"export/bibtex"
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
    g.request_start_time = time.time()
    g.request_time = lambda: "%.5fs" % (time.time() - g.request_start_time)
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
            'fl': 'title,bibcode,author,keyword,pub,aff,volume,year,[citations],property,pubdate,abstract,esources,data,publisher,comment,doi',
            'q': 'bibcode:{0}'.format(bibcode),
            'rows': '25',
            'sort': 'date desc, bibcode desc',
            'start': '0'
            })
    r = requests.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

def export_abstract(bibcode):
    """
    Export bibtex
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    data = {
            'bibcode': ['{0}'.format(bibcode)],
            'sort': 'date desc, bibcode desc',
            }
    r = requests.post(EXPORT_SERVICE, data=data, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

def search(q, rows=25, start=0, sort="date desc, bibcode desc"):
    """
    Execute query
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    params = urllib.urlencode({
                    'fl': 'title,abstract,comment,bibcode,author,keyword,id,citation_count,[citations],pub,aff,volume,pubdate,doi,pub_raw,page,links_data,property,esources,data,email,doctype',
                    'q': '{0}'.format(q),
                    'rows': '{0}'.format(rows),
                    'sort': '{0}'.format(sort),
                    'start': '{0}'.format(start)
                })
    r = requests.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

def process_search_results(results):
    """reformat raw solr response before converting to html"""
    author_limit = 3
    for d in results['response']['docs']:
        if d.get('author') and len(d['author']) > author_limit:
            msg = ' and {} more'.format(len(d['author']) - author_limit)
            d['author'] = d['author'][:author_limit]
            d['author'].append(msg)
    return results

@app.route('/', methods=['GET'])
def index():
    form = QueryForm(request.args)
    if len(form.q.data) > 0:
        if not form.no_redirect.data and ('reviews(' in form.q.data or
            'trending(' in form.q.data or
            'useful(' in form.q.data or
            'similar(' in form.q.data):
           return redirect('https://ui.adsabs.harvard.edu/search/q=' + form.q.data, 302)
        results = search(form.q.data, rows=form.rows.data, start=form.start.data, sort=form.sort.data)
        results = process_search_results(results)
        return render_template('index.html', auth=session['auth'], form=form, results=results['response'])
    return render_template('index.html', auth=session['auth'], form=form)

@app.route('/abs/<bibcode>/abstract', methods=['GET'])
@app.route('/abs/<bibcode>', methods=['GET'])
def abs(bibcode):
    if len(bibcode) == 19:
        results = abstract(bibcode)
        return render_template('abstract.html', auth=session['auth'], results=results['response']['docs'][0])
    return redirect(url_for('index'))

@app.route('/abs/<bibcode>/export', methods=['GET'])
def export(bibcode):
    if len(bibcode) == 19:
        results = export_abstract(bibcode)
        return render_template('export.html', auth=session['auth'], data=results['export'])
    return redirect(url_for('index'))
