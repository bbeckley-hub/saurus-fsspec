# saurus-fsspec

fsspec backend for the SAURUS Staphylococcus aureus genomic surveillance database.

```python
import pandas as pd
df = pd.read_csv("saurus://mlst")

See https://saurus-db.org/ for the full data resource.
