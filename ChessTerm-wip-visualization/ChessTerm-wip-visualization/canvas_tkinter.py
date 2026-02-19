from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk
from chess import *
import threading

# Variables globales - Taille réduite
board_width = 640
board_height = 640


class Chess_UI:
    """
    Gère l'affichage du plateau d'échecs.
    Le calcul de l'IA tourne dans un thread séparé pour ne pas geler l'interface.
    """

    def __init__(self, root, board, J_Blanc, J_Noir):
        # Définition des images pour les pièces
        piece_size = 70
        self.img_dict = {
            'p': ImageTk.PhotoImage(Image.open('img/pion_noir.png').resize((piece_size, piece_size))),
            'b': ImageTk.PhotoImage(Image.open('img/fou_noir.png').resize((piece_size, piece_size))),
            'q': ImageTk.PhotoImage(Image.open('img/reine_noire.png').resize((piece_size, piece_size))),
            'k': ImageTk.PhotoImage(Image.open('img/roi_noir.png').resize((piece_size, piece_size))),
            'n': ImageTk.PhotoImage(Image.open('img/cavalier_noir.png').resize((piece_size, piece_size))),
            'r': ImageTk.PhotoImage(Image.open('img/tour_noire.png').resize((piece_size, piece_size))),
            'P': ImageTk.PhotoImage(Image.open('img/pion_blanc.png').resize((piece_size, piece_size))),
            'B': ImageTk.PhotoImage(Image.open('img/fou_blanc.png').resize((piece_size, piece_size))),
            'Q': ImageTk.PhotoImage(Image.open('img/reine_blanche.png').resize((piece_size, piece_size))),
            'K': ImageTk.PhotoImage(Image.open('img/roi_blanc.png').resize((piece_size, piece_size))),
            'N': ImageTk.PhotoImage(Image.open('img/cavalier_blanc.png').resize((piece_size, piece_size))),
            'R': ImageTk.PhotoImage(Image.open('img/tour_blanche.png').resize((piece_size, piece_size))),
        }

        self.root = root
        self.board = board
        self.Joueur_Blanc = J_Blanc
        self.Joueur_Noir = J_Noir
        self.mainframe = ttk.Frame(self.root)
        self.mainframe.grid()

        # Canvas pour l'échiquier
        self.canvas = Canvas(
            self.mainframe,
            bg="black",
            width=board_width,
            height=board_height
        )
        self.canvas.grid(row=0, column=0)

        # Charger l'image du plateau
        self.bg_img = Image.open('img/plateau.png').resize((board_width, board_height))
        self.bg_photo = ImageTk.PhotoImage(self.bg_img)
        self.canvas.create_image(board_width / 2, board_height / 2, image=self.bg_photo)

        # Historique à droite
        history_frame = Frame(self.mainframe, bg="white")
        history_frame.grid(row=0, column=1, sticky=(N, S), padx=10)

        Label(history_frame, text="Historique", bg="white", font=("Arial", 12, "bold")).pack()

        self.history_text = Text(history_frame, width=20, height=35, font=("Courier", 10))
        self.history_text.pack()

        scrollbar = Scrollbar(history_frame, command=self.history_text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.history_text.config(yscrollcommand=scrollbar.set)

        # Label de statut (indique quand l'IA réfléchit)
        self.status_label = Label(
            self.mainframe,
            text="",
            font=("Arial", 11, "italic"),
            fg="blue",
            bg="white"
        )
        self.status_label.grid(row=1, column=0, columnspan=2, pady=4)

        self.pieces_list = []
        self._computing = False
        self.update_board()

        # Lancer le premier coup après 1 seconde
        self.root.after(1000, self.jouer)

    # ------------------------------------------------------------------
    # Méthodes utilitaires
    # ------------------------------------------------------------------

    def get_x_from_col(self, col: int) -> float:
        return board_width / 8 * col + board_width / 16

    def get_y_from_row(self, row: int) -> float:
        return board_height / 8 * row + board_height / 16

    def display_piece(self, piece, col: int, row: int) -> None:
        self.pieces_list.append(
            self.canvas.create_image(
                self.get_x_from_col(col),
                self.get_y_from_row(row),
                image=self.img_dict[piece]
            )
        )

    def update_board(self):
        """Mise à jour visuelle du plateau (toujours appelé depuis le thread principal)."""
        for piece in self.pieces_list:
            self.canvas.delete(piece)
        self.pieces_list = []

        row = 0
        col = 0
        for piece in self.board.board_fen():
            if '1' <= piece <= '8':
                col += ord(piece) - ord('0')
            elif piece == '/':
                col = 0
                row += 1
            else:
                self.display_piece(piece, col, row)
                col += 1

        self.root.update_idletasks()

    def add_to_history(self, coup, is_white):
        if is_white:
            self.history_text.insert(END, f"{self.board.fullmove_number}. {coup}  ")
        else:
            self.history_text.insert(END, f"{coup}\n")
        self.history_text.see(END)

    # ------------------------------------------------------------------
    # Logique de jeu avec threading
    # ------------------------------------------------------------------

    def jouer(self):
        """
        Point d'entrée pour chaque coup.
        Vérifie la fin de partie, puis délègue le calcul à un thread.
        """
        if self._computing:
            return  # Sécurité : ne pas lancer deux calculs simultanément

        # Vérification de la victoire
        if self.board.is_game_over():
            res = self.board.result()
            if res == "1-0":
                res = "Blancs gagnent !"
            elif res == "0-1":
                res = "Noirs gagnent !"
            else:
                res = "Égalité !"

            self.canvas.create_rectangle(120, 270, 520, 370, fill="white", outline="red", width=4)
            self.canvas.create_text(
                320, 320,
                text=f"Partie terminée\n{res}",
                font=("Arial", 24, "bold"),
                fill="red"
            )
            self.status_label.config(text="")
            return

        self._computing = True

        # Lancer le calcul dans un thread séparé pour ne pas geler Tkinter
        thread = threading.Thread(target=self._calcul_coup, daemon=True)
        thread.start()

    def _calcul_coup(self):
        """
        Exécuté dans un thread secondaire.
        Calcule le coup, puis repasse la main au thread principal via `after`.
        """
        try:
            if self.board.turn == WHITE:
                coup = self.Joueur_Blanc.coup()
                is_white = True
                print(f"Blancs : {coup}")
            else:
                coup = self.Joueur_Noir.coup()
                is_white = False
                print(f"Noirs : {coup}")

            # Repasser au thread principal pour modifier le board et l'UI
            self.root.after(0, lambda: self._appliquer_coup(coup, is_white))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._computing = False

    def _appliquer_coup(self, coup, is_white):
        """
        Appelé depuis le thread principal après le calcul.
        Met à jour le board, l'historique et l'affichage.
        """
        try:
            self.add_to_history(coup, is_white)
            self.board.push_san(coup)
            self.update_board()
        except Exception as e:
            print(f"Erreur lors de l'application du coup '{coup}': {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._computing = False
            self.status_label.config(text="")
            # Prochain coup après 300 ms
            self.root.after(300, self.jouer)
