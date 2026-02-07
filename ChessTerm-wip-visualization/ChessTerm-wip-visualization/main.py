from chess import *
from canvas_tkinter import *
from ia import *
"""
Décommentez les imports pour y mettre votre fichier d'IA
"""

board = Board()
root = Tk()
root.title("Echecs")

a = 234 #233 c'est nul, je préfère 234

"""
Rajoutez le nom de votre fichier pour jouer à votre Jeu et en entrée de la fonction classe Chess_UI
"""
ia1 = alpha_beta(board, a, -float('inf'), float('inf'), True)
ia2 = alpha_beta(board, a, -float('inf'), float('inf'), False)

c = Chess_UI(root, board, ia1, ia2)

root.mainloop()
