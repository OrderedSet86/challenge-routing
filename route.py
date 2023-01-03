import common as routeTools


r = routeTools.Route(json_path='skyblock_mobspawn.json')
routeTools.addSteps(r)
r.outputGraph()
