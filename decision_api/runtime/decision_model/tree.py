"""Predefined DAG routing. Model choices can only select existing edges."""
import math


def validate_tree(tree):
    nodes = tree['nodes']
    if tree['root'] not in nodes:
        raise ValueError('Unknown root')
    visiting, done = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('Workflow contains a cycle')
        if key in done:
            return
        if key not in nodes:
            raise ValueError(f'Unknown destination: {key}')
        visiting.add(key)
        node = nodes[key]
        if not node.get('terminal', False):
            actions = node['actions']
            ids = [a['id'] for a in actions]
            if not actions or len(set(ids)) != len(ids):
                raise ValueError('Actions must have distinct IDs')
            if not node.get('question') or any(not a.get('description') for a in actions):
                raise ValueError('Question and action descriptions are required')
            for action in actions:
                visit(action['next'])
        elif node.get('actions'):
            raise ValueError('Terminal node cannot have actions')
        visiting.remove(key)
        done.add(key)
    for key in nodes:
        visit(key)


def node_request(tree, node_id, context, history=()):
    node = tree['nodes'][node_id]
    if node.get('terminal'):
        raise ValueError('Cannot score a terminal node')
    # IDs and array positions never enter candidate text.
    state = context
    if history:
        state += '\nCompleted workflow steps:\n' + '\n'.join(h['description'] for h in history)
    if node.get('protocol'):
        state += '\nProtocol for this node:\n' + node['protocol']
    return state, [{'question': node['question'],
                    'choices': [a['description'] for a in node['actions']]}]


def choose_action(actions, probabilities):
    if len(actions) != len(probabilities) or not actions:
        raise ValueError('Score/action mismatch')
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError('Invalid probabilities')
    if not math.isclose(sum(probabilities), 1, abs_tol=1e-4):
        raise ValueError('Probabilities must sum to one')
    # Exact ties break by stable action ID, independent of input ordering.
    return min(range(len(actions)), key=lambda i: (-probabilities[i], actions[i]['id']))


def route(tree, context, predictor, max_steps=64):
    validate_tree(tree)
    node_id, path = tree['root'], []
    while not tree['nodes'][node_id].get('terminal'):
        if len(path) >= max_steps:
            raise ValueError('Workflow step limit exceeded')
        state, questions = node_request(tree, node_id, context, path)
        probabilities = predictor.predict(state, questions)['probabilities'][0]
        actions = tree['nodes'][node_id]['actions']
        index = choose_action(actions, probabilities)
        action = actions[index]
        path.append({'node': node_id, 'action': action['id'], 'description': action['description'],
                     'next': action['next'], 'scores': dict(zip([a['id'] for a in actions], probabilities))})
        node_id = action['next']
    return {'terminal': node_id, 'path': path, 'tree_version': tree.get('version')}
