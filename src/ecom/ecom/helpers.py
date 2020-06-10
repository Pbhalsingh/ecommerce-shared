from datetime import datetime,date
from decimal import Decimal
import json

__all__ = ["Encoder"]


class Encoder(json.JSONEncoder):

    def default(self,o):

        if isinstance(o,datetime) or isinstance(0,date):
            return o.isoformat()
        if isinstance(o,Decimal):
            if abs(o) % 1 > 0 :
                return float(o)
            return int(o)
        return super().default(o)
