import sys
import os
import json
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QSystemTrayIcon, QMenu, QSizePolicy, QFrame,
    QPushButton, QLineEdit, QTextEdit, QDialog, QFormLayout,
    QDateTimeEdit, QDialogButtonBox, QMessageBox
)
from PyQt6.QtGui import QIcon, QAction, QDrag
from PyQt6.QtCore import QTimer, QDateTime, Qt, QMimeData, pyqtSignal

try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None

APP_NAME = "OrganizadorDeTarefas"
APP_TITLE = "Organizador de Tarefas"
APP_TOOLTIP = "Organizador de Tarefas"

APP_DATA_DIR = os.path.join(os.environ['APPDATA'], APP_NAME)
os.makedirs(APP_DATA_DIR, exist_ok=True)
KANBAN_DB_FILE = os.path.join(APP_DATA_DIR, "kanban.db")

APP_ICON_FILE = "icon.ico"

DARK_MODE_STYLESHEET = """
QWidget {
    background-color: #2B2B2B;
    color: #F0F0F0;
    font-family: Arial, sans-serif;
}
QMainWindow {
    background-color: #2B2B2B;
}
QFrame#KanbanColumn {
    background-color: #3C3C3C;
    border-radius: 5px;
}
QLabel#ColumnTitle {
    color: #FFFFFF;
    font-weight: bold;
    font-size: 16px;
    padding: 5px;
    background-color: transparent;
}
QFrame#TaskCard {
    background-color: #4A4A4A;
    border: 1px solid #555555;
    border-radius: 5px;
    padding: 5px;
    min-height: 120px;
}
QLabel#CardTitle {
    color: #FFFFFF;
    font-weight: bold;
    font-size: 14px;
    background-color: transparent;
}
QLabel#CardInfo {
    color: #DDDDDD;
    font-size: 10px;
    background-color: transparent;
}
QPushButton#AddTaskButton {
    background-color: #0078D7;
    color: #FFFFFF;
    border: none;
    padding: 8px;
    border-radius: 4px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#AddTaskButton:hover {
    background-color: #005A9E;
}
QWidget#CardButtonContainer {
    background-color: transparent;
}
QPushButton#EditButton {
    background-color: #5A5A5A;
    color: #FFFFFF;
    border: none;
    padding: 4px 8px;
    font-size: 10px;
    border-radius: 3px;
}
QPushButton#EditButton:hover {
    background-color: #6A6A6A;
}
QPushButton#DeleteButton {
    background-color: #C42B1C;
    color: #FFFFFF;
    border: none;
    padding: 4px 8px;
    font-size: 10px;
    border-radius: 3px;
}
QPushButton#DeleteButton:hover {
    background-color: #A42B1C;
}
QDialog {
    background-color: #2B2B2B;
}
QLineEdit, QTextEdit, QDateTimeEdit {
    background-color: #3C3C3C;
    color: #F0F0F0;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px;
}
QTextEdit {
    min-height: 60px;
}
QDateTimeEdit::drop-down {
    border: none;
    background-color: #4A4A4A;
}
QDateTimeEdit::down-arrow {
    width: 10px;
    height: 10px;
}
QDialogButtonBox QPushButton {
    background-color: #4A4A4A;
    color: #FFFFFF;
    border: 1px solid #555555;
    padding: 5px 15px;
    border-radius: 4px;
    min-width: 60px;
}
QDialogButtonBox QPushButton:hover {
    background-color: #5A5A5A;
}
QDialogButtonBox QPushButton:default {
    background-color: #0078D7;
    border: none;
}
QDialogButtonBox QPushButton:default:hover {
    background-color: #005A9E;
}
"""

class BaseTaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(350)
        
        self.layout = QFormLayout(self)
        
        self.titulo_edit = QLineEdit(self)
        self.layout.addRow("Título:", self.titulo_edit)
        
        self.desc_edit = QTextEdit(self)
        self.desc_edit.setPlaceholderText("(Opcional)")
        self.layout.addRow("Descrição:", self.desc_edit)
        
        self.datetime_edit = QDateTimeEdit(self)
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.datetime_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.layout.addRow("Prazo Final:", self.datetime_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        self.layout.addRow(button_box)

    def get_data(self):
        return {
            "titulo": self.titulo_edit.text(),
            "descricao": self.desc_edit.toPlainText(),
            "notificar_em": self.datetime_edit.dateTime().toPyDateTime()
        }

    def set_data(self, data):
        self.titulo_edit.setText(data.get('titulo', ''))
        self.desc_edit.setPlainText(data.get('descricao', ''))
        
        notificar_em = data.get('notificar_em')
        if not notificar_em:
            notificar_em = QDateTime.currentDateTime()
        elif isinstance(notificar_em, str):
            try:
                if '.' in notificar_em:
                    notificar_em = notificar_em.split('.')[0]
                notificar_em = QDateTime.fromString(notificar_em, "yyyy-MM-dd HH:mm:ss")
            except:
                 notificar_em = QDateTime.currentDateTime()
        elif isinstance(notificar_em, datetime):
            notificar_em = QDateTime(notificar_em)
        
        if not notificar_em.isValid() or notificar_em.isNull():
             notificar_em = QDateTime.currentDateTime()
             
        self.datetime_edit.setDateTime(notificar_em)

class NewTaskDialog(BaseTaskDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar Nova Tarefa")

class EditTaskDialog(BaseTaskDialog):
    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Tarefa")
        self.set_data(task_data)

class TaskCard(QFrame):
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setObjectName("TaskCard")
        
        layout = QVBoxLayout()
        
        self.titulo_label = QLabel(self.task_data['titulo'])
        self.titulo_label.setObjectName("CardTitle")
        layout.addWidget(self.titulo_label)
        
        if self.task_data.get('descricao'):
            desc_label = QLabel(self.task_data['descricao'])
            desc_label.setWordWrap(True)
            desc_label.setObjectName("CardInfo")
            layout.addWidget(desc_label)
        
        if self.task_data.get('notificar_em'):
            data_notificacao_str = self.task_data['notificar_em']
            data_str = ""
            if data_notificacao_str:
                try:
                    if '.' in data_notificacao_str:
                        data_notificacao_str = data_notificacao_str.split('.')[0]
                    data_notificacao_obj = datetime.strptime(data_notificacao_str, "%Y-%m-%d %H:%M:%S")
                    data_str = data_notificacao_obj.strftime('%d/%m/%Y %H:%M')
                except ValueError:
                    data_str = "Data inválida"
            
            if data_str:
                notif_label = QLabel(f"📅 Prazo Final: {data_str}")
                notif_label.setObjectName("CardInfo")
                layout.addWidget(notif_label)
        
        layout.addStretch()
        
        button_container = QWidget(self)
        button_container.setObjectName("CardButtonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0,0,0,0)
        button_layout.addStretch()
        
        edit_button = QPushButton("Editar")
        edit_button.setObjectName("EditButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(self.on_edit_clicked)
        
        delete_button = QPushButton("Excluir")
        delete_button.setObjectName("DeleteButton")
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.clicked.connect(self.on_delete_clicked)
        
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        layout.addWidget(button_container)
        
        self.setLayout(layout)

    def on_edit_clicked(self):
        self.edit_requested.emit(self.task_data['id'])

    def on_delete_clicked(self):
        self.delete_requested.emit(self.task_data['id'])

    def mouseMoveEvent(self, e):
        if e.buttons() != Qt.MouseButton.LeftButton:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.task_data['id']))
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab()) 
        
        self.hide() 
        drop_action = drag.exec(Qt.DropAction.MoveAction)

        if drop_action == Qt.DropAction.MoveAction:
            self.deleteLater()
        else:
            self.show()

class KanbanColumn(QFrame):
    card_dropped = pyqtSignal(int, str)
    
    def __init__(self, title, column_id, parent=None):
        super().__init__(parent)
        self.column_id = column_id
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("KanbanColumn")
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        
        self.title_label = QLabel(title)
        self.title_label.setObjectName("ColumnTitle")
        self.layout.addWidget(self.title_label)
        
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout()
        self.card_layout.setContentsMargins(0,0,0,0)
        self.card_layout.setSpacing(5)
        self.card_container.setLayout(self.card_layout)
        
        self.layout.addWidget(self.card_container)
        self.layout.addStretch()
        
        self.setLayout(self.layout)
        self.setAcceptDrops(True)

    def add_card(self, card_widget):
        self.card_layout.addWidget(card_widget)

    def clear_cards(self):
        while self.card_layout.count():
            child = self.card_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def dragEnterEvent(self, e):
        if e.mimeData().hasText() and isinstance(e.source(), TaskCard):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if isinstance(e.source(), TaskCard):
            task_id = int(e.mimeData().text())
            self.card_dropped.emit(task_id, self.column_id)
            e.acceptProposedAction()

class MainWindow(QMainWindow):
    def __init__(self, db_connection_func):
        super().__init__()
        self.db_connection_func = db_connection_func
        
        self.setWindowTitle(APP_TITLE)
        self.setGeometry(100, 100, 1000, 700)
        
        if os.path.exists(APP_ICON_FILE):
            self.setWindowIcon(QIcon(APP_ICON_FILE))
        
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        self.add_task_button = QPushButton("➕ Nova Tarefa")
        self.add_task_button.setObjectName("AddTaskButton")
        self.add_task_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_task_button.clicked.connect(self.open_new_task_dialog)
        main_layout.addWidget(self.add_task_button)
        
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        
        self.coluna_todo = KanbanColumn("A Fazer", "todo")
        self.coluna_doing = KanbanColumn("Fazendo", "doing")
        self.coluna_done = KanbanColumn("Feito", "done")
        
        self.coluna_todo.card_dropped.connect(self.on_card_moved)
        self.coluna_doing.card_dropped.connect(self.on_card_moved)
        self.coluna_done.card_dropped.connect(self.on_card_moved)
        
        columns_layout.addWidget(self.coluna_todo)
        columns_layout.addWidget(self.coluna_doing)
        columns_layout.addWidget(self.coluna_done)
        
        main_layout.addWidget(columns_widget)
        self.setCentralWidget(main_widget)
        
        self.load_and_display_tasks()

    def load_and_display_tasks(self):
        self.coluna_todo.clear_cards()
        self.coluna_doing.clear_cards()
        self.coluna_done.clear_cards()
        
        tasks = self.load_tasks_from_db()
        
        for task in tasks:
            task_dict = dict(task) 
            card = TaskCard(task_dict)
            card.edit_requested.connect(self.on_edit_task)
            card.delete_requested.connect(self.on_delete_task)
            
            if task_dict['coluna'] == 'todo':
                self.coluna_todo.add_card(card)
            elif task_dict['coluna'] == 'doing':
                self.coluna_doing.add_card(card)
            elif task_dict['coluna'] == 'done':
                self.coluna_done.add_card(card)

    def on_card_moved(self, task_id, new_column_id):
        conn = self.db_connection_func()
        if conn is None:
            QMessageBox.warning(self, "Erro de DB", "Não foi possível conectar ao DB para mover a tarefa.")
            self.load_and_display_tasks()
            return
            
        cursor = conn.cursor()
        try:
            query = "UPDATE tasks SET coluna = ? WHERE id = ?"
            cursor.execute(query, (new_column_id, task_id))
            conn.commit()
            self.load_and_display_tasks() 
                
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Erro de DB", f"Erro ao atualizar coluna: {e}")
            self.load_and_display_tasks()
        finally:
            conn.close()

    def load_tasks_from_db(self, task_id=None):
        conn = self.db_connection_func()
        if conn is None:
            return [] if task_id is None else None
            
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor() 
        
        if task_id:
            query = "SELECT * FROM tasks WHERE id = ?"
            try:
                cursor.execute(query, (task_id,))
                task = cursor.fetchone()
                return task
            except sqlite3.Error as e:
                print(f"Erro ao buscar tarefa {task_id}: {e}")
                return None
            finally:
                conn.close()
        else:
            tasks = []
            try:
                cursor.execute("SELECT * FROM tasks ORDER BY data_criacao DESC")
                tasks = cursor.fetchall()
            except sqlite3.Error as e:
                print(f"Erro ao buscar tarefas: {e}")
            finally:
                conn.close()
            return tasks

    def open_new_task_dialog(self):
        dialog = NewTaskDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['titulo']:
                QMessageBox.warning(self, "Erro", "O título da tarefa não pode ser vazio.")
                return
            
            self.db_insert_task(data)
            self.load_and_display_tasks()

    def db_insert_task(self, data):
        conn = self.db_connection_func()
        if conn is None:
            QMessageBox.warning(self, "Erro de DB", "Não foi possível conectar ao DB para criar a tarefa.")
            return

        query = """
            INSERT INTO tasks (titulo, descricao, notificar_em, coluna) 
            VALUES (?, ?, ?, 'todo')
        """
        values = (
            data['titulo'], 
            data['descricao'], 
            data['notificar_em'].strftime("%Y-%m-%d %H:%M:%S")
        )
        
        cursor = conn.cursor()
        try:
            cursor.execute(query, values)
            conn.commit()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Erro de DB", f"Erro ao inserir tarefa: {e}")
        finally:
            conn.close()

    def on_edit_task(self, task_id):
        task_data_row = self.load_tasks_from_db(task_id=task_id)
        if not task_data_row:
            QMessageBox.warning(self, "Erro", "Não foi possível carregar a tarefa para edição.")
            return
        
        task_data = dict(task_data_row)
        dialog = EditTaskDialog(task_data, self)
        
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data['titulo']:
                QMessageBox.warning(self, "Erro", "O título da tarefa não pode ser vazio.")
                return
            
            self.db_update_task(task_id, new_data)
            self.load_and_display_tasks()
            
    def db_update_task(self, task_id, data):
        conn = self.db_connection_func()
        if conn is None:
            QMessageBox.warning(self, "Erro de DB", "Não foi possível conectar ao DB para atualizar a tarefa.")
            return

        query = """
            UPDATE tasks SET 
                titulo = ?, 
                descricao = ?, 
                notificar_em = ?,
                notificado = 0, 
                notificado_10d = 0, 
                notificado_5d = 0, 
                notificado_1d = 0
            WHERE id = ?
        """
        values = (
            data['titulo'], 
            data['descricao'], 
            data['notificar_em'].strftime("%Y-%m-%d %H:%M:%S"),
            task_id
        )
        
        cursor = conn.cursor()
        try:
            cursor.execute(query, values)
            conn.commit()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Erro de DB", f"Erro ao atualizar tarefa: {e}")
        finally:
            conn.close()

    def on_delete_task(self, task_id):
        reply = QMessageBox.question(self, "Confirmar Exclusão",
                                     "Tem certeza que deseja excluir esta tarefa?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db_delete_task(task_id)
            self.load_and_display_tasks()
            
    def db_delete_task(self, task_id):
        conn = self.db_connection_func()
        if conn is None:
            QMessageBox.warning(self, "Erro de DB", "Não foi possível conectar ao DB para excluir a tarefa.")
            return
            
        cursor = conn.cursor()
        try:
            query = "DELETE FROM tasks WHERE id = ?"
            cursor.execute(query, (task_id,))
            conn.commit()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Erro de DB", f"Erro ao excluir tarefa: {e}")
        finally:
            conn.close()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class KanbanApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyleSheet(DARK_MODE_STYLESHEET)
        
        self.app.setQuitOnLastWindowClosed(False) 
        self.toaster = ToastNotifier() if ToastNotifier else None
        
        if not self.init_db():
            QMessageBox.critical(None, "Erro de Banco de Dados", 
                "Não foi possível criar ou conectar ao banco de dados SQLite 'kanban.db'.\n"
                "Verifique as permissões da pasta.\n"
                "O aplicativo será fechado.")
            sys.exit(1)
            
        self.window = MainWindow(self.create_db_connection)
        
        self.setup_tray_icon()
        self.setup_notification_timer()

        self.window.tray_icon = self.tray_icon 
        self.window.show()

    def run(self):
        sys.exit(self.app.exec())

    def create_db_connection(self):
        try:
            connection = sqlite3.connect(KANBAN_DB_FILE)
            return connection
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao SQLite: {e}")
            return None

    def init_db(self):
        conn = self.create_db_connection()
        if conn is None:
            return False
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            coluna TEXT NOT NULL DEFAULT 'todo',
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            notificar_em DATETIME,
            notificado INTEGER NOT NULL DEFAULT 0,
            notificado_10d INTEGER NOT NULL DEFAULT 0,
            notificado_5d INTEGER NOT NULL DEFAULT 0,
            notificado_1d INTEGER NOT NULL DEFAULT 0
        );
        """
        try:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            print(f"Banco de dados '{KANBAN_DB_FILE}' inicializado com sucesso.")
            return True
        except sqlite3.Error as e:
            print(f"Erro ao criar tabela: {e}")
            return False
        finally:
            conn.close()
        
    def setup_tray_icon(self):
        icon_path = APP_ICON_FILE
        
        if not os.path.exists(icon_path):
            print(f"Aviso: '{icon_path}' não encontrado. Usando ícone padrão do sistema.")
            style = self.app.style()
            icon = QIcon(style.standardPixmap(style.StandardPixmap.SP_ComputerIcon))
        else:
            print(f"Usando ícone: {icon_path}")
            icon = QIcon(icon_path)
        
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip(APP_TOOLTIP)
        
        tray_menu = QMenu()
        show_action = QAction("Abrir " + APP_TITLE, self.app)
        show_action.triggered.connect(self.window.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        quit_action = QAction("Sair", self.app)
        quit_action.triggered.connect(self.app.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.window.show()
                self.window.activateWindow()

    def setup_notification_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_for_notifications)
        self.timer.start(60 * 1000) 
        self.check_for_notifications()

    def check_for_notifications(self):
        print(f"[{QDateTime.currentDateTime().toString()}] Verificando banco de dados SQLite...")
        
        conn = self.create_db_connection()
        if conn is None:
            return

        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        try:
            query_10d = """
                SELECT * FROM tasks 
                WHERE notificar_em <= datetime('now', 'localtime', '+10 days')
                  AND notificar_em > datetime('now', 'localtime', '+5 days')
                  AND notificado_10d = 0 
                  AND notificar_em IS NOT NULL
            """
            cursor.execute(query_10d)
            for tarefa in cursor.fetchall():
                print(f"Disparando aviso (10D): {tarefa['titulo']}")
                self.show_notification(
                    f"Aviso: {tarefa['titulo']}",
                    f"Faltam 10 dias para sua tarefa."
                )
                self.db_update_warning_status(tarefa['id'], "notificado_10d")

            query_5d = """
                SELECT * FROM tasks 
                WHERE notificar_em <= datetime('now', 'localtime', '+5 days')
                  AND notificar_em > datetime('now', 'localtime', '+1 day')
                  AND notificado_5d = 0 
                  AND notificar_em IS NOT NULL
            """
            cursor.execute(query_5d)
            for tarefa in cursor.fetchall():
                print(f"Disparando aviso (5D): {tarefa['titulo']}")
                self.show_notification(
                    f"Atenção: {tarefa['titulo']}",
                    f"Faltam 5 dias para sua tarefa."
                )
                self.db_update_warning_status(tarefa['id'], "notificado_5d")
                
            query_1d = """
                SELECT * FROM tasks 
                WHERE notificar_em <= datetime('now', 'localtime', '+1 day')
                  AND notificar_em > datetime('now', 'localtime')
                  AND notificado_1d = 0 
                  AND notificar_em IS NOT NULL
            """
            cursor.execute(query_1d)
            for tarefa in cursor.fetchall():
                print(f"Disparando aviso (1D): {tarefa['titulo']}")
                self.show_notification(
                    f"Urgente: {tarefa['titulo']}",
                    f"Falta 1 dia para sua tarefa!"
                )
                self.db_update_warning_status(tarefa['id'], "notificado_1d")

            query_now = """
                SELECT * FROM tasks 
                WHERE notificar_em <= datetime('now', 'localtime')
                  AND notificado = 0 
                  AND notificar_em IS NOT NULL
            """
            cursor.execute(query_now)
            for tarefa in cursor.fetchall():
                print(f"Disparando notificação FINAL: {tarefa['titulo']}")
                self.show_notification(
                    f"Lembrete: {tarefa['titulo']}",
                    f"Sua tarefa '{tarefa['titulo']}' está agendada para agora."
                )
                self.db_update_warning_status(tarefa['id'], "notificado")

        except sqlite3.Error as e:
            print(f"Erro ao verificar notificações: {e}")
        finally:
            conn.close()

    def db_update_warning_status(self, task_id, column_name):
        allowed_columns = ['notificado', 'notificado_10d', 'notificado_5d', 'notificado_1d']
        if column_name not in allowed_columns:
            print(f"Erro: Tentativa de atualizar coluna inválida: {column_name}")
            return

        conn = self.create_db_connection()
        if conn is None:
            return
            
        cursor = conn.cursor()
        try:
            query = f"UPDATE tasks SET {column_name} = 1 WHERE id = ?"
            cursor.execute(query, (task_id,))
            conn.commit()
            print(f"Tarefa {task_id} marcada como '{column_name}'.")
        except sqlite3.Error as e:
            print(f"Erro ao atualizar status da tarefa {task_id}: {e}")
        finally:
            conn.close()

    def show_notification(self, title, message):
        if self.toaster:
            try:
                self.toaster.show_toast(
                    title,
                    message,
                    duration=10,
                    threaded=True
                )
            except Exception as e:
                print(f"Erro ao mostrar notificação: {e}")
        else:
            print(f"NOTIFICAÇÃO (simulada): {title} - {message}")
            if self.tray_icon:
                 self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 10000)

if __name__ == "__main__":
    app = KanbanApp()
    app.run()