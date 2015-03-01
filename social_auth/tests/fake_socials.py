from collections import Counter
import random
import urlparse
import urllib
import json
import re
import logging
import itertools

logger = logging.getLogger(__name__)

def randbool():
    return random.randint(0,1) == 0

FACEBOOK_PAGE_SIZE = 300
def facebook_id_generator(uid):
    return '%d'%(uid,)
friend_facebook_ids = [ facebook_id_generator(i) for i in range(2000,2400) ]
facebook_fofs = {}
times_fofs_called = 0
paging_pat = re.compile(r'offset=([0-9]+)')
guaranteed_nonprivate_uids = Counter()
expired_auths = Counter()

class number_of_social_friends():
    def __init__(self, num):
        self.num = num

    def __enter__(self):
        global friend_facebook_ids
        self.old_friend_facebook_ids = friend_facebook_ids
        friend_facebook_ids = map(facebook_id_generator, range(2000, 2000+self.num))

    def __exit__(self, type, value, traceback):
        global friend_facebook_ids
        friend_facebook_ids = self.old_friend_facebook_ids

class make_auth_expired():
    def __init__(self, network):
        self.key = network
    def __enter__(self):
        expired_auths[self.key] += 1
    def __exit__(self, type, value, traceback):
        expired_auths[self.key] -= 1

class make_social_profile_non_private():
    def __init__(self, uid):
        self.uid = uid
    def __enter__(self):
        guaranteed_nonprivate_uids[self.uid] += 1
    def __exit__(self, type, value, traceback):
        guaranteed_nonprivate_uids[self.uid] -= 1

class FakeHttpResponse(object):
    def __init__(self, status_code=None, content=None):
        self.status_code = status_code
        self.content = content

locations = ['Georgetown, IL', 'Tel Aviv', 'Jerusalem', 'New York, New York', 'New Haven, MA', u'\u05de\u05d2\u05d3\u05dc \u05d4\u05e2\u05de\u05e7']
li_locations = [('Georgetown, IL', 'usa'), ('Jerusalem, Israel', 'il'), ('New York, New York', 'usa'), ('New Haven, MA', 'usa'), (u'\u05de\u05d2\u05d3\u05dc \u05d4\u05e2\u05de\u05e7', 'il')]
like_categories = ['Stuff A', 'Stuff B', 'Stuff C', u'\u05e2\u05e0\u05d9\u05d9\u05e0\u05d9\u05dd' ]
like_names = [ 'Gays', 'Straights', 'Transes', u'\u05e2\u05dc\u05d9\u05d6\u05d5\u05ea' ]
tag_repo = ['Java', 'C', 'C++', 'Big Data', 'Small Data', 'Medium-Sized Data', 'Matlab', 'Physics']
fake_companies = list(itertools.chain(* [ map(lambda x: '%s%03x'%(x,i,), ['Microsoft', 'Google', 'Samsung', 'Yahoo', 'Lenovo', u'\u05d1\u05e0\u05e7', u'\u05db\u05d9"\u05dc']) for i in range(5) ]))
tickers = {'Microsoft000': 'MSFT', 'Google001': 'GOOG', 'Samsung002': 'SMSG', 'Yahoo003': 'YHOO', 'Lenovo004': 'LNVO', u'\u05db\u05d9"\u05dc': 'KIL', }

def fake_http(*args, **kwargs):
    import urllib
    url = kwargs['url']
    assert url is not None
    url = urlparse.urlparse(url)
    if url.path.endswith('jpg'):
        return FakeHttpResponse(status_code=200, content='abc')
    if 'linkedin' in url.netloc:
        return fake_linkedin(*args, **kwargs)
    if 'facebook' in url.netloc:
        return fake_facebook(*args, **kwargs)
    assert False

def random_company(id_maker):
    name = random.choice(fake_companies)
    idd = id_maker(name)
    ticker = tickers.get(name)
    if randbool():
        name = '%s %s'%(name, random.choice(suffixes))
    ret = {'name': name}
    if idd:
        ret['id'] = idd
    if ticker:
        ret['ticker'] = ticker
    return ret


######################################
# LINKEDIN
######################################
def linkedin_company_id(name):
    ind = fake_companies.index(name)
    if ind % 3 != 0:
        ret = 'LI%x'%(ind,)
        if randbool():
            ret = 'Z' + ret
        return ret
    else:
        return None

suffixes = ['Ltd', 'Co', 'Inc']

def li_decorate_length(parent, child):
    c = len(parent.get(child, []))
    parent['@total'] = str(c)
    if c == 1:
        parent[child], = parent.pop(child)

def random_linkedin_date():
    ret = {'year': random.randint(1990, 2020)}
    if randbool():
        ret['month'] = random.randint(1,12)
        if randbool():
            ret['day'] = random.randint(1,28)
    return ret

def random_linkedin_company(with_urls=False):
    ret = random_company(linkedin_company_id)
    if with_urls:
        if randbool():
            ret['website-url'] = '%swww.example.com'%('http://' if randbool() else '')
        if randbool():
            ret['logo-url'] = '%swww.example.com/logo.jpg'%('http://' if randbool() else '')
    # TODO industries
    return ret

def random_linkedin_profile(fid, fields):
    is_private = not guaranteed_nonprivate_uids[fid] and random.randint(0, 10) == 0
    out = {}
    for f in fields: # 'id', 'first-name', 'last-name', 'picture-url', 'positions', 'educations', 'headline', 'industry', 'location',
        if is_private:
            if f in ('id', 'last-name'):
                out[f] = 'private'
            continue
        if f == 'id':
            out[f] = fid
        elif f == 'first-name':
            out[f] = 'Fn%s'%(fid,) if randbool() else u'\u05e9\u05dd%s'%(fid,)
        elif f == 'last-name':
            out[f] = 'Ln%s'%(fid,) if randbool() else u'\u05e4\u05e9\u05dd%s'%(fid,)
        elif f == 'picture-url':
            out[f] = 'http://i.am.an.example.com/linkedin.jpg'
        elif f == 'educations':
            out[f] = {'education': []}
            edus = out[f]['education']
            for i in range(random.randint(0, 5)):
                edu = {}
                edu['school-name'] = 'school%d'%(random.randint(0,10),) if random.randint(0,10)>0 else u'\u05d1\u05d9\u05ea \u05e1\u05e4\u05e8'
                if randbool():
                    edu['id'] = random.randint(1,10000)
                # TODO field-of-study, degree, activities, notes
                if randbool():
                    edu['start-date'] = {'year': random.randint(1990,2020), }
                    if randbool():
                        edu['end-date'] = {'year': edu['start-date']['year'] + random.randint(0,4), }
                if not edu:
                    continue
                edus.append(edu)
            assert all(e is not None for e in edus)
            li_decorate_length(out[f], 'education')
            assert all(e is not None for e in edus)
        elif f == 'positions':
            out[f] = {'position': []}
            poss = out[f]['position']
            for i in range(random.randint(0, 5)):
                pos = {}
                for name in ('id', 'title', 'summary'):
                    if randbool():
                        pos[name] = 'Position Title #%d'%(random.randint(0,1000)) if randbool() else u'\u05e1\u05d1\u05d0 \u05d5\u05e1\u05d1\u05ea\u05d0 #%d'%(random.randint(0,100))
                if randbool():
                    pos['start-date'] = random_linkedin_date()
                if randbool():
                    pos['end-date'] = random_linkedin_date()
                pos['is-current'] = 'true' if randbool() else 'false'
                pos['company'] = random_linkedin_company() if random.randint(0,40)>0 else None
                poss.append(pos)
            li_decorate_length(out[f], 'position')
        elif f == 'location':
            loc_i = random.randint(0, len(li_locations)-1)
            name, country_code = li_locations[loc_i]
            out[f] = {'name': locations[loc_i], 'country': {'code': country_code, } }
        elif f in ('headline', 'industry'):
            pass # TBD
        elif f == 'public-profile-url':
            if randbool():
                out[f] = 'http://www.linkedin.com/i/have/some/profile-name/%s'%(fid, )
        elif f == 'skills':
            num_tags = random.randint(0,10)
            if num_tags > 0:
                out[f] = {'skill': []}
                for i in range(random.randint(0,10)):
                    tagid = random.randint(0, len(tag_repo)-1)
                    out[f]['skill'].append({'id': tagid,
                                            'skill': {'name': tag_repo[tagid], },
                                            })
                li_decorate_length(out[f], 'skill')
        else:
            raise Exception('Unrecognized social field: %s'%(f, ))
    return out

fields_pat = re.compile(r'(https?://[^:]+):\(([-:()a-z,]+)\)(.*)')

def fake_linkedin(*args, **kwargs):
    import xmltodict
    url = kwargs.pop('url')
    params = kwargs.pop('params', {})
    if expired_auths['LI']:
        return FakeHttpResponse(status_code=401, content='joo have been expired')
    m = fields_pat.match(url)
    if m:
        fields = set(m.group(2).split(','))
        url = m.group(1) + m.group(3)
    else:
        fields = set()
    fields.add('id')
    assert url is not None
    url = urlparse.urlparse(url)
    assert url.scheme == 'https'
    if url.path == '/v1/people/~':
        with make_social_profile_non_private('1234'):
            ret = {'person': random_linkedin_profile('1234', fields)}
    elif url.path == '/v1/people/~/connections':
        if 'public-profile-url' in fields:
            return FakeHttpResponse(status_code=500, content="you may not ask for public-profile-url of friends")
        ret = {'connections': { 'person': [ random_linkedin_profile(fid, fields.difference('skills')) for fid in friend_facebook_ids ]}}
        li_decorate_length(ret['connections'], 'person')
    elif url.path == '/v1/company-search':
        ret = {'company-search': {'companies': {'company': []}}}
        for i in range(random.randint(0, 5)):
            comp = random_linkedin_company(with_urls=True)
            ret['company-search']['companies']['company'].append(comp)
        li_decorate_length(ret['company-search']['companies'], 'company')
    else:
        raise Exception('Unrecognized linkedin URL: %s'%(url.path))
    logger.debug('fake linkedin returning: %s'%(unicode(ret)[:50],))
    return FakeHttpResponse(status_code=200, content=xmltodict.unparse(ret))




######################################
# FACEBOOK
######################################

def init_fake_facebook(friendship_pairs):
    global facebook_fofs
    facebook_fofs = {}
    [ facebook_fofs.setdefault(unicode(a), set()).add(unicode(b)) for a,b in friendship_pairs ]
    [ facebook_fofs.setdefault(unicode(a), set()).add(unicode(b)) for b,a in friendship_pairs ]

def rand_facebook_date(null_probability=0.1):
    if random.random() < null_probability:
        return '0000-00'
    else:
        return '%4d-%02d-%02d'%(random.randint(1990,2020), random.randint(1,12), random.randint(1,28))

def rand_like():
    out = {'category': random.choice(like_categories)}
    out['name'] = random.choice(like_names)
    out['id'] = random.randint(10,50)
    if randbool():
        out['category_list'] = []
        for i in range(random.randint(1,3)):
            out['category_list'].append({'id': random.randint(10,50), 'name': random.choice(like_names), })
    return out

def facebook_company_id(name):
    ind = fake_companies.index(name)
    if ind % 2 == 0:
        ind = 'FB%s'%(ind,)
        if randbool():
            ind = 'LLL' + ind
        return ind
    else:
        return None

def random_facebook_company():
    return random_company(facebook_company_id)

def random_facebook_profile(fid, fields):
    out = {}
    for f in fields: # 'first_name','last_name','name','picture.type(normal)','education','work','hometown','location']
        if f == 'id':
            out[f] = fid
        elif f == 'first_name':
            out[f] = 'Fn%s'%(fid,) if randbool() else u'\u05e9\u05dd%s'%(fid,)
        elif f == 'last_name':
            out[f] = 'Ln%s'%(fid,) if randbool() else u'\u05e9\u05dd %s'%(fid,)
        elif f == 'name':
            out[f] = 'Fn%s U. Ln%s'%(fid, fid, ) if randbool() else u'\u05e1\u05d1\u05d0 \u05d5\u05e1\u05d1\u05ea\u05d0 %s'%(fid, )
        elif f.startswith('picture'):
            out['picture'] = {'data': {'url': 'http://i.am.an.example.com/bubu.jpg', 'is_silhoutte': randbool(), }, }
        elif f == 'education':
            for i in range(random.randint(0, 5)):
                edu = {}
                edu['school'] = {}
                if randbool():
                    edu['school']['id'] = 'school%d'%(random.randint(0,10))
                edu['school']['name'] = 'school%d'%(random.randint(0,100)) if randbool() else u'\u05d1\u05d9\u05ea \u05e1\u05e4\u05e8 %s'%(random.randint(0,10))
                if randbool():
                    edu['year'] = random.randint(1990,2020)
                out.setdefault(f, []).append(edu)
        elif f == 'work':
            for i in range(random.randint(0, 5)):
                pos = {}
                pos['employer'] = random_facebook_company()
                if randbool():
                    pos['position'] = {'name': 'i am teh guy' if randbool() else u'\u05e1\u05d1\u05d0 \u05d5\u05e1\u05d1\u05ea\u05d0', }
                if random.randint(0, 10) > 0:
                    pos['start_date'] = rand_facebook_date(0.3)
                if random.randint(0, 10) > 8:
                    pos['end_date'] = rand_facebook_date(0.1)
                out.setdefault(f, []).append(pos)
        elif f in ('hometown', 'location'):
            if randbool():
                loc_i = random.randint(0, len(locations)-1)
                out[f] = {'name': locations[loc_i], 'id': loc_i, }
        elif f in ('groups', 'likes'):
            assert fid == 1234, 'Expecting only user 1234 to request groups/likes, got %s instead'%(fid, )
            if randbool():
                out[f] = {'data': []}
                for i in range(random.randint(1, 5)):
                    out[f]['data'].append(rand_like())
        else:
            raise Exception('Unrecognized social field: %s'%(f, ))
    return out

def fake_facebook__times_fof_called():
    global times_fofs_called
    return times_fofs_called

fql_pat = re.compile(r'uid2 in \((.*)\)')
def fake_facebook(*args, **kwargs):
    global times_fofs_called
    global facebook_fofs
    if expired_auths['FB']:
        return FakeHttpResponse(status_code=400, content=json.dumps({'error': {'message': 'joo have been expired'}}))
    url = urlparse.urlparse(kwargs['url'])
    query = dict(urlparse.parse_qsl(url.query + urllib.urlencode(kwargs.pop('params', {}))))
    fields = set(query.get('fields', 'id').split(','))
    fields.add('id')
    assert url.scheme == 'https'
    if url.path == '/me/':
        ret = random_facebook_profile(1234, fields)
    elif url.path == '/me/friends':
        m = paging_pat.search(url.query)
        if m:
            start_at = int(m.group(1))
        else:
            start_at = 0
        end_at = min(start_at + FACEBOOK_PAGE_SIZE, len(friend_facebook_ids)+1)
        at_end = (end_at > len(friend_facebook_ids))
        ret = {'data': [ random_facebook_profile(fid, fields) for fid in friend_facebook_ids[start_at:end_at] ]}
        if not at_end:
            ret['paging'] = {'next': '%s://%s%s?%s&limit=%d&offset=%d'%(url.scheme, url.netloc, url.path, urllib.urlencode(query),
                                                                                  FACEBOOK_PAGE_SIZE, end_at,)}
    elif url.path == '/fql/':
        times_fofs_called += 1
        fql_q = query.pop('q')
        ids_match = fql_pat.search(fql_q)
        assert ids_match, "Couldn't find IDs in %s"%(fql_q,)
        ids_str = ids_match.group(1)
        ids = ids_str.split(',')
        assert set(friend_facebook_ids).issuperset(ids)
        assert set(ids).intersection(friend_facebook_ids), '%s'%(ids,)
        logger.debug('fake facebook FQL for IDs: %s'%(ids,))
        ret = {'data': [ {'uid1': uid1, 'uid2': uid2} for uid1 in ids for uid2 in facebook_fofs.get(uid1, []) ]}
    else:
        raise Exception('Unrecognized facebook URL: %s'%(url.path))
    return FakeHttpResponse(status_code=200, content=json.dumps(ret))
