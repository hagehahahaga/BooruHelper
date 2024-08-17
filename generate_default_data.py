import pickle
import pathlib


def generate():
    pathlib.Path('data.pickle').write_bytes(
        pickle.dumps(
            {
                'download_queue': [],
                'tag_num': 0,
                'tag_values': {},
                'disliked_ids': [],
                'cache': {}
            }
        )
    )


var = {
    'download_queue': [int],
    'tag_num': 0,
    'tag_values': {str: float | int},
    'disliked_ids': [int],
    'cache': {
        tuple: {
            'searched': bool,
            'cache': [int]
        }
    }
}