from pathlib import Path
import hashlib

class CacheManager:
    def __init__(self, cache_dir: str | Path = './.cache.d') -> None:
        self.cache_dir = Path(cache_dir)
        if not self.cache_dir.exists():
            self.cache_dir.mkdir()
        elif not self.cache_dir.is_dir():
            self.cache_dir.unlink()
    
    def _calc_hash(self, content: str | bytes) -> str:
        if isinstance(content, str):
            content = content.encode()
        return hashlib.sha512(content).hexdigest()

    def has_cache(self, content: str) -> bool:
        content_hash = self._calc_hash(content)
        cache_file = self.cache_dir / f'{content_hash}.psap'
        return cache_file.exists()

    def find_cache_for_content(self, content: str) -> str | None:
        content_hash = self._calc_hash(content)
        cache_file = self.cache_dir / f'{content_hash}.psap'
        if cache_file.exists():
            with cache_file.open() as f:
                return f.read()
    
    def find_cache_for_file(self, file: str | Path) -> str | None:
        with Path(file).open() as f:
            return self.find_cache_for_content(f.read())

    def write_cache_of_chart(self, chart: str | Path, cache: str):
        content_hash = self._calc_hash(Path(chart).open().read())
        with (self.cache_dir / f'{content_hash}.psap').open('w') as out:
            out.write(cache)
    
    def write_cache_of_content(self, content: str, cache: str):
        content_hash = self._calc_hash(content)
        with (self.cache_dir / f'{content_hash}.psap').open('w') as out:
            out.write(cache)


__all__ = ['CacheManager']