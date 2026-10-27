import re,json,sys
FUT=re.compile(r'(\d+(?:\.\d+)?) \((\w{3} \d\d)\)')
def parse(path, slug):
    out=[];fut=[];commod=None;mkt=None
    rd=None
    for line in open(path):
        line=line.rstrip('\n')
        m=re.search(r'Grain Report for (\d\d/\d\d/\d{4}) - (\w+)',line)
        if m: rd=m.group(1);status=m.group(2)
        m=re.match(r'\s+(CBOT|KCBT|MGE)\s+(.+?)\s{2,}(\d.*)$',line)
        if m:
            for p,c in FUT.findall(m.group(3)): fut.append(dict(exchange=m.group(1),commodity=m.group(2).strip(),price_cents_bu=float(p),contract=c))
        m=re.match(r'\s+((?:US #|Canola|White Millet|Flax)[^\n]*?)\s*(\(Bulk\))?\s*$',line)
        if m and 'Bulk' in line: commod=m.group(1).strip(); continue
        if re.match(r'^(Country Elevators|Terminal|Mills|Barge|Delivered)',line.strip()) and ' - ' in line: mkt=line.strip(); continue
        # data row
        m=re.match(r'\s*(?P<loc>[A-Za-z .,]+?)\s+(?P<sale>Bid|Nominal|Trade)\s+(?P<prot>\d+\.\d%|Ordinary)?\s*(?P<basis>-?\d+\.\d\d[A-Z]?(?: to -?\d+\.\d\d[A-Z]?)?)?\s+(?P<bchg>(?:UNCH|UP|DN)[^\s]*(?: \d+\.\d\d)?(?:-(?:UNCH|UP \d+\.\d\d|DN \d+\.\d\d))?)?\s*(?P<price>\d+\.\d{2,4}(?:-\d+\.\d{2,4})?)\s+(?P<pchg>(?:UNCH|UP|DN)(?: \d+\.\d+)?(?:-(?:UNCH|UP \d+\.\d+|DN \d+\.\d+))?)\s+(?P<avg>\d+\.\d+)(?:\s+(?P<ya>\d+\.\d+))?\s+(?P<frt>[A-Z]+-[A-Z/]+)\s+(?P<deliv>\w+)',line)
        if m and commod:
            g=m.groupdict()
            out.append(dict(slug=slug,report_date=rd,commodity=commod,market_type=mkt,region=g['loc'].strip(),sale_type=g['sale'],protein=g['prot'],basis_raw=g['basis'],basis_change_raw=g['bchg'],price_raw=g['price'],price_change_raw=g['pchg'],avg_price=float(g['avg']),year_ago_avg=float(g['ya']) if g['ya'] else None,freight=g['frt'],delivery=g['deliv']))
    return fut,out
if __name__=='__main__':
    f,o=parse(sys.argv[1],sys.argv[2]); json.dump(dict(futures=f,rows=o),open(sys.argv[2]+'.parsed.json','w'),indent=1); print(sys.argv[2],len(f),len(o))
