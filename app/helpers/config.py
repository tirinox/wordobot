import sys
from typing import Any

import yaml
from dotenv import load_dotenv

from helpers.date_utils import parse_timespan_to_seconds


class SubConfig:
    def __init__(self, config_data):
        self._root_config = config_data

    def get(self, path: str = None, default=None, pure=False) -> 'SubConfig':
        if path is None or path == '':
            return self._root_config

        if isinstance(path, int):
            # single number => subscript of list
            components = [path]
        else:
            components = map(str.strip, path.split('.'))

        sub_config = self._root_config
        try:
            for component in components:
                if isinstance(sub_config, (list, tuple)):
                    sub_config = sub_config[int(component)]
                elif isinstance(sub_config, dict):
                    sub_config = sub_config[component]

            if isinstance(sub_config, (list, tuple, dict)):
                # collection => SubConfig(it)
                return (
                    sub_config if pure else SubConfig(sub_config)
                ) if default is None else sub_config
            else:
                # primitive => always pure!
                return sub_config
        except (KeyError, IndexError) as e:
            # fixme: ?? print(e)
            if default is not None:
                return default
            else:
                raise

    def get_pure(self, path=None, default=None) -> Any:
        return self.get(path, default, pure=True)

    def as_int(self, path: str = None, default=None):
        return int(self.get(path, default))

    def as_float(self, path: str = None, default=None):
        return float(self.get(path, default))

    def as_str(self, path: str = None, default=None):
        return str(self.get(path, default))

    def as_list(self, path: str = None, default=None):
        return list(self.get(path, default)._root_config)

    @property
    def as_seconds(self):
        return parse_timespan_to_seconds(self._root_config)

    def __int__(self):
        return int(self._root_config)

    def __float__(self):
        return float(self._root_config)

    def __str__(self):
        return str(self._root_config)

    def __getattr__(self, item) -> 'SubConfig':
        return self.get(item)

    def __getitem__(self, item) -> 'SubConfig':
        return self.get(item)


class Config(SubConfig):
    DEFAULT = '../config.yaml'
    DEFAULT_ENV_FILE = '.env'

    def __init__(self, name=None, data=None):
        load_dotenv(self.DEFAULT_ENV_FILE)

        if data is None:
            if name:
                self._config_name = name
            else:
                self._config_name = sys.argv[1] if len(sys.argv) >= 2 else self.DEFAULT

            with open(self._config_name, 'r') as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)

        super().__init__(data)
