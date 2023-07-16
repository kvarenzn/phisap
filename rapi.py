from typing import NamedTuple, Generic, TypeVar, TypedDict
import json
from pathlib import Path
import requests


class RTokens(NamedTuple):
    token: str
    refresh_token: str


class RChartInfo(TypedDict):
    id: int
    name: str
    level: str
    difficulty: float
    charter: str
    composer: str
    illustrator: str
    description: str
    ranked: bool
    reviewed: bool
    stable: bool
    stable_request: bool

    illustraion: str
    preview: str
    file: str

    uploader: int
    created: str
    updated: str
    chart_updated: str

    tags: list[str]
    rating: float | None


class RChartInfoDict(TypedDict):
    id: int
    name: str
    level: str
    difficulty: float
    charter: str
    composer: str
    illustrator: str
    description: str
    ranked: bool
    reviewed: bool
    stable: bool
    stable_request: bool

    illustraion: str
    preview: str
    file: str

    uploader: int
    created: str
    updated: str
    chart_updated: str

    tags: list[str]
    rating: float | None


class RProfile(TypedDict):
    id: int
    name: str
    avatar: str
    badge: str
    language: str
    bio: str | None
    exp: int
    rks: float
    joined: str
    last_login: str
    roles: int
    role: str
    follower_count: int
    following_count: int


T = TypeVar('T')


class RResult(TypedDict, Generic[T]):
    count: int
    results: list[T]


class RApi:
    _BASE_URL = 'https://api.phira.cn'
    session: requests.Session
    tokens: RTokens | None
    token_cache: Path
    profile: RProfile | None  # profile is None means not logged in

    def __init__(self, token_cache_path: str):
        self.session = requests.Session()
        self.session.headers['Accept-Language'] = 'zh-CN'
        self.token_cache = Path(token_cache_path)
        self.profile = None
        self.tokens = None
        if self.token_cache.exists():
            self.load_token()

    def reqwest(self, method: str, path_or_url: str, **kwargs) -> requests.Response:
        # request with authorization
        if self.tokens is None:
            raise RuntimeError('need login')
        url = self._BASE_URL + path_or_url if path_or_url.startswith('/') else path_or_url
        authorization = {'Authorization': f'Bearer {self.tokens.token}'}
        if 'headers' in kwargs:
            kwargs['headers'] |= authorization
        else:
            kwargs['headers'] = authorization
        return self.session.request(method, url, **kwargs)

    def load_token(self):
        with self.token_cache.open('r') as tin:
            token = json.load(tin)
            self.tokens = RTokens(token['token'], token['refresh_token'])

    def save_token(self):
        if self.tokens is None:
            return

        with self.token_cache.open('w') as out:
            json.dump({'token': self.tokens.token, 'refresh_token': self.tokens.refresh_token}, out)

    def login(self, email: str, password: str) -> None:
        result = self.session.post(self._BASE_URL + '/login', json={'email': email, 'password': password}).json()

        if 'error' in result:
            raise RuntimeError(f'login failed: {result["error"]}')

        self.tokens = RTokens(result['token'], result['refreshToken'])
        self.save_token()

    def me(self) -> dict:
        return self.reqwest('GET', '/me').json()

    def download(self, url: str) -> bytes:
        res = self.reqwest('GET', url)
        if res.status_code != 200:
            raise RuntimeError('Download failed')
        return res.content

    def chart_search(self, query: dict | None = None) -> RResult[RChartInfo]:
        if query is None:
            query = {}
        if 'page' not in query:
            query['page'] = 1
        return self.session.get(self._BASE_URL + '/chart', params=query).json()

    def chart_info(self, id: int) -> RChartInfoDict:
        return self.session.get(f'{self._BASE_URL}/chart/{id}').json()

    def record(self, query: dict | None = None) -> dict:
        if query is None:
            query = {}
        if 'page' not in query:
            query['page'] = 1
        return self.session.get(self._BASE_URL + '/record', params=query).json()

    def refresh_token(self) -> None:
        if not self.tokens:
            return
        result = self.session.post(self._BASE_URL + '/login', json={'refreshToken': self.tokens.refresh_token}).json()
        print(result)
        if 'error' in result:
            raise RuntimeError(f'refresh token failed: {result["error"]}')
        self.tokens = RTokens(result['token'], result['refreshToken'])
        self.save_token()
