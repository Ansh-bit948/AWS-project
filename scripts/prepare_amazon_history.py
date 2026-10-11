"""Stream genuine Amazon access-change history and evaluate observed-outcome Q-learning."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://archive.ics.uci.edu/dataset/216/amazon+access+samples'
DOWNLOAD='https://archive.ics.uci.edu/static/public/216/amazon+access+samples.zip'

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

def main():
    rawdir=ROOT/'data/raw';rawdir.mkdir(exist_ok=True)
    archive=rawdir/'amazon_access_samples.zip'
    if not archive.exists():
        urllib.request.urlretrieve(DOWNLOAD,archive)
    tgz=rawdir/'amzn-anon-access-samples.tgz'
    if not tgz.exists():
        with zipfile.ZipFile(archive) as z:
            tgz.write_bytes(z.read('amzn-anon-access-samples.tgz'))
    history=rawdir/'amazon_access_history.csv'
    if not history.exists():
        with tarfile.open(tgz,'r:gz') as t:
            for member in t:
                if member.name.endswith('history-2.0.csv'):
                    with history.open('wb') as dest:
                        src=t.extractfile(member)
                        while True:
                            block=src.read(1024*1024)
                            if not block:break
                            dest.write(block)
                    break
    events=[];invalid=Counter()
    with history.open(encoding='utf-8-sig',newline='') as f:
        for line,r in enumerate(csv.DictReader(f),2):
            if r['ACTION'] not in ('add_access','remove_access'):
                invalid['unknown_action']+=1;continue
            try:
                requested=datetime.strptime(r['REQUEST_DATE'],'%Y-%m-%d %H:%M:%S')
                authorized=datetime.strptime(r['AUTHORIZATION_DATE'],'%Y-%m-%d %H:%M:%S')
            except (ValueError,TypeError):
                invalid['missing_or_invalid_timestamp']+=1;continue
            delay=(authorized-requested).total_seconds()
            if delay<0:
                invalid['negative_authorization_delay']+=1;continue
            if not r['LOGIN'] or not r['TARGET_NAME']:
                invalid['missing_identifier']+=1;continue
            events.append((authorized,requested,line,r['LOGIN'],r['TARGET_NAME'],r['ACTION'],delay))
    events.sort()
    counts=Counter(x[5] for x in events);split=int(len(events)*.8)
    # Partition by timestamp so simultaneous events cannot leak across the boundary.
    boundary=events[split][0]
    train=[e for e in events if e[0]<boundary]
    test=[e for e in events if e[0]>=boundary]
    seen=Counter();removes=Counter();targets=defaultdict(set);profiles=defaultdict(lambda:{'count':0,'add':0,'remove':0,'first':None,'last':None})
    q=defaultdict(lambda:[0.,0.]);support=Counter();scores=[]
    train_actions=Counter(e[5] for e in train)
    majority=max(train_actions,key=train_actions.get)
    agreement=0;baseline_agree=0;abstained=0;matched_rewards=[]
    for index,e in enumerate(events):
        authorized,requested,line,u,p,action,delay=e
        # Features contain only this user's preceding changes and the current request hour.
        state=f"volume:{min(5,int(math.log2(seen[u]+1)))}|remove:{int(removes[u]*2/max(1,seen[u]))}|hour:{requested.hour//6}"
        ai=0 if action=='add_access' else 1
        # Recorded fulfillment delay is the only outcome signal; no invented risk/approval reward.
        reward=-min(1.,math.log1p(delay)/math.log1p(86400))
        if authorized<boundary:
            q[state][ai]+=.1*(reward-q[state][ai])
            support[(state,ai)]+=1
        else:
            possible=[i for i in (0,1) if support[(state,i)]>=5]
            prediction=max(possible,key=lambda i:q[state][i]) if possible else None
            if prediction is None:abstained+=1
            else:
                agreement+=int(prediction==ai)
                if prediction==ai:matched_rewards.append(reward)
            baseline_agree+=int(action==majority)
        seen[u]+=1;removes[u]+=int(action=='remove_access');targets[u].add(p)
        item=profiles[u];item['count']+=1;item['add']+=int(action=='add_access');item['remove']+=int(action=='remove_access')
        item['first']=item['first'] or authorized.isoformat();item['last']=authorized.isoformat()
    covered=len(test)-abstained
    result={'experiment':'Amazon enterprise access-change history','source_url':SOURCE,'citation':'Montanez, K. (2011). Amazon Access Samples. DOI:10.24432/C5JW2K',
      'license':'CC BY 4.0','archive_sha256':sha(archive),'history_sha256':sha(history),'measured_at_utc':datetime.now(timezone.utc).isoformat(),
      'counts':{'valid_events':len(events),'users':len(profiles),'targets':len({e[4] for e in events}),'actions':dict(counts),'excluded_rows':dict(invalid)},
      'time_range':{'first':events[0][0].isoformat(),'last':events[-1][0].isoformat()},
      'model':{'algorithm':'Offline terminal Q-learning / contextual bandit; gamma=0, alpha=0.1','actions':['add_access','remove_access'],
               'state':'Only preceding per-user change count, removal fraction and request-hour bucket','reward':'-min(1, log(1+recorded authorization delay seconds)/log(1+86400)); observed action only',
               'action_mask':'Require at least 5 observed training examples for a state/action; otherwise abstain',
               'q_table':dict(q),'training_records':len(train),'heldout_records':len(test),'split_timestamp':boundary.isoformat()},
      'evaluation':{'split':'Chronological 80/20; whole timestamps remain in one partition','coverage':covered/len(test),'abstained':abstained,
                    'observed_action_agreement':agreement/covered if covered else None,'majority_action_baseline':majority,
                    'majority_baseline_agreement':baseline_agree/len(test),
                    'matched_action_mean_reward':sum(matched_rewards)/len(matched_rewards) if matched_rewards else None,
                    'limit':'Agreement is descriptive; recorded delay reflects observational selection. No causal/off-policy utility or safety guarantee.'},
      'profile_samples':[{'user_id':u,'access_change_count':p['count'],'add_count':p['add'],'remove_count':p['remove'],
                          'unique_targets':len(targets[u]),'first_change':p['first'],'last_change':p['last']} for u,p in sorted(profiles.items())[:50]],
      'limits':['History records are actual enterprise access changes, not ERP transactions or authentication events.',
                'The 4.8 GB wide access snapshot is not expanded or falsely reported as processed.',
                'Target IDs keep the source identifiers; no business semantics or HR fields are invented.',
                'The model runs on published historical outcomes and never changes benchmark policy or AWS IAM.']}
    out=ROOT/'data/processed/amazon_history_analysis.json'
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/amazon-evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('counts','time_range','evaluation')},indent=2))
if __name__=='__main__':main()
