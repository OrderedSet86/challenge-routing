# Standard libraries
import itertools
import json # TODO: Switch to YAML
import os
from collections import defaultdict
from pathlib import Path

# Pypi libraries
import graphviz
import whoosh.query
from termcolor import cprint
from whoosh.fields import ID, Schema, TEXT
from whoosh.index import create_in

# TODO:
# 1. ~~Import whoosh search for titles (actually add details as well)~~
# 2. ~~Add writer for route to file~~
# 3. ~~Finish user dialog~~
# 4. ~Add graphviz charting~
# 5. Add grouping



class Step:

    def __init__(
            self,
            idx: int,
            title: str,
            details: str,
            products: list[str],
            prereqs: dict[str, list[str]],
        ):
        self.idx = idx
        self.title = title
        self.details = details
        self.products = products
        self.prereqs = prereqs
    
    def __repr__(self):
        return '\n'.join([
            f'{self.idx=}',
            f'{self.title=}',
            f'{self.details=}',
            f'{self.products=}',
            f'{self.prereqs=}',
        ])
    
    def toDict(self):
        return {
            'index': self.idx,
            'title': self.title,
            'details': self.details,
            'products': self.products,
            'prereqs': self.prereqs,
        }



class Group:

    def __init__(self, title, steps=None):
        self.title = title
        if self.steps is None:
            self.steps = []
        self.steps = steps



class Route:


    def __init__(self, steps=None, json_path=None):
        self.json_path = json_path

        if json_path is not None:
            if not Path(json_path).exists():
                with open(json_path, 'w') as f:
                    f.write('[]')

            with open(json_path, 'r') as f:
                db = json.load(f)
            self.steps = []
            ordering = [
                'index',
                'title',
                'details',
                'products',
                'prereqs',
            ]
            for step in db:
                elements = [step[key] for key in ordering]
                self.steps.append(Step(*elements))

        else:
            self.json_path = 'temp.json'
            if steps is None:
                steps = []
            self.steps = steps

        self.indices = {}
        self._computeRouteTable()


    def _computeRouteTable(self):
        # Compute tables:
        # 1. id -> step
        # 2. output -> parent step id (defaultdict[list])
        # 3. search tree for titles

        # Table 1
        self.lookup_step = {}
        self.lookup_step, self.max_idx = self.__addIDToLookupStepFromIterable(self.steps, self.lookup_step, 0)

        # Table 2
        self.lookup_parent = defaultdict(list)
        self.__addOutputToLookupParent(self.steps, self.lookup_parent)

        # Table 3
        schema = Schema(index=ID(stored=True), content=TEXT(stored=True))

        os.makedirs('db/titles', exist_ok=True)
        ix = create_in("db/titles", schema)
        writer = ix.writer()

        # Add contents to table 3
        for step in self.steps:
            writer.add_document(
                index=f'{step.idx}',
                content=f'{step.title}',
            )

        writer.commit()
        self.indices['titles'] = ix


        os.makedirs('db/products', exist_ok=True)
        ix = create_in("db/products", schema)
        writer = ix.writer()
        
        # Add contents to table 3
        for step in self.steps:
            for i, product in enumerate(step.products):
                writer.add_document(
                    index=f'{step.idx}-{i}',
                    content=f'{product}',
                )

        writer.commit()
        self.indices['products'] = ix


    def __addIDToLookupStepFromIterable(self, iterable, lookup, max_idx):
        for step in iterable:
            if isinstance(step, Step):
                lookup[step.idx] = step
                max_idx = max(max_idx, step.idx)
            elif isinstance(step, Group):
                for substep in step.steps:
                    _, max_idx = self.__addIDToLookupStepFromIterable(substep, lookup, max_idx)
        
        return lookup, max_idx


    def __addOutputToLookupParent(self, iterable, lookup):
        for step in iterable:
            if isinstance(step, Step):
                for output in step.products:
                    lookup[output].append(step.idx)
            elif isinstance(step, Group):
                for substep in step.steps:
                    _ = self.__addOutputToLookupParent(substep, lookup)

        return lookup


    def search(self, index, string):
        if index == 'all':
            index = ['titles', 'products']
        elif isinstance(index, str):
            index = [index]
        
        start = 1

        for ix in index:
            actual = self.indices[ix]
            with actual.searcher() as searcher:
                query = whoosh.query.Variations('content', string)
                results = searcher.search(query)

                if len(results):
                    print(f'Results for index "{ix}":')

                    match_by_idx = {}

                    for i, hit in zip(range(start, 100000), results):
                        fields = hit.fields()

                        match_by_idx[i] = fields['content']

                        cprint(i, 'yellow', end=' ')
                        cprint(fields['content'], 'green', end='')
                        if ix == 'products':
                            parent_index = int(fields['index'].split('-')[0]) - 1
                            cprint(f' ({self.steps[parent_index].title})', 'blue')
                        else:
                            print()

                    print()
                    start += len(results)

                    user_idx = int(strictInput('What index corresponds to your intention?', [lambda x: x.isdigit()]))
                    if user_idx == 0:
                        return None
                    parent_index = int(results[user_idx - 1].fields()['index'].split('-')[0]) - 1
                    parent_step = self.steps[parent_index]
                    return (parent_step.idx, match_by_idx[user_idx])
                else:
                    return None


    def convertToJSON(self):
        return [x.toDict() for x in self.steps]


    def outputGraph(self, collapseGroups=True):
        # TODO: Add support for collapseGroups
        node_style = {
            'shape': 'box',
            'style': 'filled',
        }
        g = graphviz.Digraph(
            engine='dot',
            strict=False, # Prevents edge grouping
            graph_attr={
                'splines': 'true',
                'rankdir': 'TD',
                'ranksep': '0.5',
                # 'overlap': 'scale',
                'bgcolor': '#043742',
                # 'mindist': '0.1',
                # 'overlap': 'false',
                'nodesep': '0.1',
            }
        )
        
        EDGECOLOR_CYCLE = [
            '#b58900', # 'yellow'
            '#cb4b16', # 'orange'
            '#dc322f', # 'red'
            '#d33682', # 'magenta'
            '#6c71c4', # 'violet'
            '#268bd2', # 'blue'
            '#2aa198', # 'cyan'
            '#859900', # 'green'
        ]        
        color_cycler = itertools.cycle(EDGECOLOR_CYCLE)

        for step in self.steps:
            label = '\n'.join([
                step.title,
                # *step.products
            ])

            g.node(
                str(step.idx),
                label=label,
                fontname='arial',
                fontsize='11',
                **node_style,
            )
            for parent_idx, itemlist in step.prereqs.items():
                label = '\n'.join(itemlist)
                color = next(color_cycler)
                g.edge(
                    str(parent_idx),
                    str(step.idx),
                    label=label,
                    color=color,
                    fontname='arial',
                    fontsize='10',
                    fontcolor=color
                )

        g.render(
            str(Path(self.json_path).name)[:-5],
            'output/',
            view=True,
            format='png',
        )



def simpleYN(user_in):
    user_in = user_in.strip()
    if len(user_in) != 1:
        return False
    if user_in not in 'YyNn':
        return False
    return True



def strictInput(message, expectations):
    # expectations is a list of functions to apply to the input. they must all return true
    previously_failed = False
    while True:
        if previously_failed:
            user_in = input(f'X {message} ')
        else:
            user_in = input(f'  {message} ')
        valid = [f(user_in) for f in expectations]
        if all(valid):
            return user_in



def addSingleStep(route, step):
    route.steps.append(step)
    # TODO: These next steps are horribly inefficient but they'll do for the beginning
    route._computeRouteTable()
    js = route.convertToJSON()
    with open(route.json_path, 'w') as f:
        json.dump(js, f, indent=4)


def addSteps(route):
    while True:
        ans = strictInput('Would you like to enter another step? [y/n]', [simpleYN])
        enter_another = ans in 'Yy'
        if not enter_another:
            break

        title = input('Step title? ').lower()
        details = input('Step details? ').lower()
        products = input('Products from step? Please separate with semicolons (;).\n ')
        products = [x.strip() for x in products.split(';')]
        
        ans = strictInput('Would you like to add prereqs? [y/n] ', [simpleYN])
        adding_prereqs = ans in 'Yy'
        prereqs = {}
        if adding_prereqs:
            looped = False

            while True:
                message = 'Enter search query (searches products): '
                if looped:
                    message = ''
                query = input(message)
                looped = True

                search_res = route.search('products', query)
                if search_res is None:
                    print('No matching search results, try again.')
                    continue
                else:
                    parent_idx, match_word = search_res
                    # parent_step = route.steps[parent_idx - 1]
                    parent_idx = str(parent_idx)
                    if parent_idx in prereqs:
                        prereqs[parent_idx].append(match_word)
                    else:
                        prereqs[parent_idx] = [match_word]
                    ans = strictInput('Adding more? [y/n] ', [simpleYN])
                    if ans in 'Yy':
                        continue
                    else:
                        break

        if len(route.steps):
            new_idx = route.steps[-1].idx + 1
        else:
            new_idx = 1

        outputStep = Step(
            new_idx,
            title,
            details,
            products,
            prereqs,
        )
        addSingleStep(route, outputStep)
