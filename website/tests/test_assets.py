"""Static deployment integrity and simplified route export checks."""
import json,re,unittest
from html.parser import HTMLParser
from pathlib import Path

PUBLIC=Path(__file__).resolve().parents[1]/'public'
class References(HTMLParser):
 def __init__(self):super().__init__();self.paths=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ('src','href') and v and not v.startswith(('http:','https:','#','data:')):self.paths.append(v)
class Assets(unittest.TestCase):
 def test_html_dependencies_exist(self):
  for path in PUBLIC.rglob('*.html'):
   parser=References();parser.feed(path.read_text())
   for reference in parser.paths:
    with self.subTest(page=path.name,asset=reference):self.assertTrue((path.parent/reference.split('?')[0]).is_file())
 def test_route_export_has_valid_stages(self):
  routes=json.loads((PUBLIC/'simulation/routes.json').read_text())['routes']
  stages={'contact','nurse','gp','assessment','specialist','imaging','bronch','biopsy','review','treatment','followup'}
  self.assertEqual(len(routes),300)
  for route in routes:
   self.assertEqual(route[0],'contact');self.assertIn(route[-1],{'treatment','followup'});self.assertTrue(set(route)<=stages)
  pairs={(a,b) for r in routes for a,b in zip(r,r[1:])}
  self.assertTrue({('contact','nurse'),('contact','gp'),('imaging','bronch'),('imaging','biopsy')}<=pairs)
 def test_module_dependencies_exist(self):
  for path in PUBLIC.rglob('*.js'):
   for dependency in re.findall(r"from ['\"](\./[^'\"]+)['\"]",path.read_text()):self.assertTrue((path.parent/dependency).is_file())
if __name__=='__main__':unittest.main()
