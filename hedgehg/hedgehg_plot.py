import matplotlib.pyplot as plt


notes = [
    (0, 493.88), # h
    (2, 659.26), # e
    (3, 587.32), # d
    (5, 392.00), # g
    (8, 329.63), # e
    (10, 493.88), # h
    (11, 392.00), # g
]

x = [note[0] + 1 for note in notes for _ in range(3)]
y = [
    y 
    for y_base in map(lambda y: y[1] + 1, notes) 
    for y in (y_base, y_base*2, y_base*4)
]
s = [25*2**s  for _ in notes for s in range(2, -1, -1)]


plt.plot((0, 0), (0, max(y) * 1.1), color='black')
plt.plot((0, max(x) * 1.1), (0, 0), color='black')
plt.scatter(x, y, color='black', s=s)

plt.axis('off')
plt.savefig('hedgehg.jpg')
