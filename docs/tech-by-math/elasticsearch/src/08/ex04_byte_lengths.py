# Tech by Math, Elasticsearch tutorial 8, exercise E7: how many values lengths 41..1000 collapse into.
from lucene_math import int_to_byte4, byte4_to_int

back = {byte4_to_int(int_to_byte4(L)) for L in range(41, 1001)}
print(len(back), sorted(back)[:8])
