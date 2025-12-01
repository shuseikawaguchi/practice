def reverse_lookup2(dic1: dict) -> dict:
    dic2 = {}
    for key, value in dic1.items():
        dic2[value] = key
    return dic2

print("反転結果:", reverse_lookup2({'apple': 3, 'pen': 5, 'orange': 7}))
