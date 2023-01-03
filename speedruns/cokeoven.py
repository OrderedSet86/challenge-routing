import common as routeTools


r = routeTools.Route(json_path='speedruns/cokeoven.json')
routeTools.addSteps(r)
r.outputGraph()
