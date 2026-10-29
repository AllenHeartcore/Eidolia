# Eidolia

<font size="5"><b>Every Stage, Every World.</b></font>

Eidolia is a Python framework for discovering, acquiring, and exploring content from idol game worlds.

**This project is in its early stages and under active development.**<br>
Its minimal first release covers two Octo-backed titles, **Gakuen Idolmaster** and **IDOLY PRIDE**.

## Usage

```python
from eidolia.profiles import GkmasProfile

profile = GkmasProfile()
catalog = profile.get_catalog()
print(catalog.revision, len(catalog))

assets = catalog.search(r"img_general_cidol.*")
assets[0].download("objects")

# offline Octo data
catalog = profile.load_catalog("octocacheevai")
catalog.export_json("catalog.json")
```

### Example overarching application

```bash
python -m pip install -e '.[media]'
python apps/sovits_dataset.py gakumas krnh --limit 20 -o voices.zip
```
