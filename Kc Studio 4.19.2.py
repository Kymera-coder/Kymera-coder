import sys
import os
import subprocess
import threading
import re
import json
import html
from google import genai
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QPlainTextEdit, QPushButton, 
                             QLineEdit, QLabel, QSplitter, QFileDialog, QFrame, QMessageBox,
                             QStatusBar, QMenu, QTreeView, QStackedWidget, QInputDialog, QDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression, QSettings, QDir, QSize, QRect
from PyQt6.QtGui import (QFont, QTextCursor, QSyntaxHighlighter, QTextCharFormat, 
                         QColor, QKeyEvent, QAction, QIcon, QFileSystemModel, QPainter)

# ==============================================================================
# ESTILO VS CODE DARK THEME
# ==============================================================================
STYLESHEET = """
    QMainWindow { background-color: #1e1e1e; }
    QWidget { color: #cccccc; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
    
    QSplitter::handle { background-color: #252526; }
    
    QFrame { border: none; }
    QFrame#Explorer { background-color: #181818; border-right: 1px solid #252526; }
    QFrame#Editor { background-color: #1e1e1e; }
    QFrame#AI_Panel { background-color: #181818; border-left: 1px solid #252526; }
    
    QLineEdit, QTextEdit, QPlainTextEdit { 
        background-color: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 4px; padding: 8px; color: #d4d4d4;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #007fd4; }
    
    QPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 4px; padding: 6px 12px; color: #cccccc; font-weight: bold; }
    QPushButton:hover { background-color: #2d2d2d; color: #ffffff; }
    
    QPushButton#RunBtn { background-color: #007fd4; color: white; border: 1px solid #007fd4;}
    QPushButton#RunBtn:hover { background-color: #005f9e; }
    
    QPushButton#ToolBtn { border: 1px solid #3c3c3c; background-color: #252526; }
    QPushButton#ToolBtn:hover { background-color: #333333; }
    
    QPushButton#SendAI { background-color: #007fd4; color: white; padding: 6px 15px; font-weight: bold; border-radius: 4px; }
    QPushButton#SendAI:hover { background-color: #005f9e; }

    QTreeView { background-color: transparent; border: none; color: #cccccc; font-size: 12px; }
    QTreeView::item:hover { background-color: #2a2d2e; }
    QTreeView::item:selected { background-color: #37373d; color: #ffffff; }

    QStatusBar { background-color: #007fd4; color: #ffffff; font-size: 12px; border: none; }
    QLabel#SectionTitle { color: #bbbbbb; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; padding: 5px 0; }
    
    QMenu { background-color: #252526; border: 1px solid #454545; padding: 4px 0; }
    QMenu::item { padding: 6px 30px 6px 20px; color: #cccccc; }
    QMenu::item:selected { background-color: #094771; color: white; }
    
    QPushButton.TabBtn { background-color: transparent; border-bottom: 2px solid transparent; padding: 5px 15px; border-radius: 0; color: #858585; text-transform: uppercase; font-size: 11px; font-weight: bold;}
    QPushButton.TabBtn:hover { color: #cccccc; }
    QPushButton.TabBtn.Active { color: #e7e7e7; border-bottom: 2px solid #e7e7e7; }
"""

# ==============================================================================
# JANELA DE LOCALIZAR E SUBSTITUIR
# ==============================================================================
class FindReplaceDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Localizar e Substituir")
        self.setFixedSize(400, 180)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; } QLineEdit { background-color: #252526; color: white; border: 1px solid #3c3c3c; padding: 8px; } QPushButton { background-color: #333333; color: white; padding: 8px; border: none; } QPushButton:hover { background-color: #444444; }")
        layout = QVBoxLayout(self)
        self.input_find = QLineEdit(); self.input_find.setPlaceholderText("Localizar...")
        layout.addWidget(self.input_find)
        self.input_replace = QLineEdit(); self.input_replace.setPlaceholderText("Substituir por...")
        layout.addWidget(self.input_replace)
        btn_layout = QHBoxLayout()
        btn_find = QPushButton("Próximo"); btn_find.clicked.connect(self.find_next)
        btn_replace = QPushButton("Substituir"); btn_replace.clicked.connect(self.replace)
        btn_replace_all = QPushButton("Tudo"); btn_replace_all.clicked.connect(self.replace_all)
        btn_layout.addWidget(btn_find); btn_layout.addWidget(btn_replace); btn_layout.addWidget(btn_replace_all)
        layout.addLayout(btn_layout)

    def find_next(self):
        t = self.input_find.text()
        if t and not self.editor.find(t): self.editor.moveCursor(QTextCursor.MoveOperation.Start); self.editor.find(t)
    def replace(self):
        if self.editor.textCursor().hasSelection(): self.editor.textCursor().insertText(self.input_replace.text())
        self.find_next()
    def replace_all(self):
        f = self.input_find.text(); r = self.input_replace.text()
        if not f: return
        self.editor.setPlainText(self.editor.toPlainText().replace(f, r))
        self.accept()

# ==============================================================================
# WORKERS E MOTORES
# ==============================================================================
class DiscoveryWorker(QThread):
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key
    def run(self):
        try:
            client = genai.Client(api_key=self.api_key)
            chat_session = client.chats.create(model="gemini-2.5-flash")
            self.finished.emit(client, chat_session)
        except Exception as e:
            self.error.emit(str(e))

class AIStreamWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, chat_session, prompt):
        super().__init__()
        self.chat_session = chat_session
        self.prompt = prompt
        self.full_response = ""
    def run(self):
        try:
            stream = self.chat_session.send_message_stream(self.prompt)
            for chunk in stream:
                if chunk.text:
                    self.full_response += chunk.text
                    self.chunk_received.emit(chunk.text)
            self.finished.emit(self.full_response)
        except Exception as e:
            self.error.emit(f"Erro na IA: {str(e)}")

class CmdWorker(QThread):
    output_ready = pyqtSignal(str)
    error_ready = pyqtSignal(str)
    def __init__(self, command, cwd):
        super().__init__()
        self.command = command
        self.cwd = cwd
    def run(self):
        try:
            process = subprocess.Popen(self.command, shell=True, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.output_ready.emit(line)
            process.wait()
            self.output_ready.emit(" \n")
            if process.returncode != 0:
                self.error_ready.emit(f"O comando retornou um erro (Código {process.returncode}).")
        except Exception as e:
            self.error_ready.emit(f"Erro Fatal no Terminal: {str(e)}\n")
            self.output_ready.emit(" \n")

class ExecWorker(QThread):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
    def run(self):
        try:
            work_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()
            if not work_dir: work_dir = os.getcwd()
            
            if sys.platform == "win32":
                subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k", sys.executable, self.file_path], cwd=work_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal", sys.executable, self.file_path], cwd=work_dir)
            else:
                subprocess.Popen(["x-terminal-emulator", "-e", f"{sys.executable} {self.file_path}"], cwd=work_dir)
        except: pass

class ExeBuilderWorker(QThread):
    output_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)
    def __init__(self, file_path, icon_path=None):
        super().__init__()
        self.file_path = file_path
        self.icon_path = icon_path
    def run(self):
        try:
            work_dir = os.path.dirname(os.path.abspath(self.file_path))
            command = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole"]
            if self.icon_path and self.icon_path.endswith('.ico'):
                command.extend(["--icon", self.icon_path])
            command.append(self.file_path)
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=work_dir)
            for line in process.stdout: self.output_ready.emit(line.strip())
            process.wait()
            self.finished.emit(process.returncode == 0)
        except Exception as e:
            self.output_ready.emit(f"Erro Fatal ao Compilar: {str(e)}")
            self.finished.emit(False)

# ==============================================================================
# ÁREA DE NUMERAÇÃO DE LINHAS E TERMINAL
# ==============================================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
    def sizeHint(self): return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.codeEditor.lineNumberAreaPaintEvent(event)

class InteractiveTerminal(QPlainTextEdit):
    cmd_finished = pyqtSignal()
    error_ready = pyqtSignal(str) 
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #111111; color: #cccccc; font-family: 'Consolas', monospace; font-size: 13px; border: none; padding: 10px;")
        self.current_dir = os.getcwd()
        self.prompt_text = f"{self.current_dir}> "
        self.appendPlainText(self.prompt_text)
        self.cmd_worker = None

    def update_dir(self, new_dir):
        self.current_dir = new_dir
        self.prompt_text = f"{self.current_dir}> "

    def clear_terminal(self):
        self.clear()
        self.appendPlainText(self.prompt_text)

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Left):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
            if cursor.selectedText() == self.prompt_text: return
            cursor.clearSelection()

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = cursor.selectedText()
            
            command = line_text[len(self.prompt_text):].strip() if line_text.startswith(self.prompt_text) else line_text.strip()
            self.appendPlainText("") 
            
            if command.lower() in ["cls", "clear"]:
                self.clear_terminal()
            elif command.lower().startswith("cd "):
                new_path = command[3:].strip()
                try:
                    os.chdir(os.path.join(self.current_dir, new_path))
                    self.update_dir(os.getcwd())
                except:
                    self.appendPlainText("Caminho não encontrado.")
                self.appendPlainText(self.prompt_text)
            elif command:
                self.executar_comando_direto(command)
            else:
                self.appendPlainText(self.prompt_text)
            return 
        super().keyPressEvent(event)

    def executar_comando_direto(self, comando):
        self.cmd_worker = CmdWorker(comando, self.current_dir)
        self.cmd_worker.output_ready.connect(self.append_output)
        self.cmd_worker.error_ready.connect(self.error_ready.emit) 
        self.cmd_worker.start()

    def append_output(self, text):
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertPlainText(text)
        if text.endswith(" \n"): 
            self.insertPlainText(self.prompt_text)
            self.cmd_finished.emit()
        self.ensureCursorVisible()

# ==============================================================================
# EDITOR INTELIGENTE E CORES
# ==============================================================================
class SmartCodeEditor(QPlainTextEdit):
    file_dropped = pyqtSignal(str) 
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 14))
        self.setTabStopDistance(40)
        self.setAcceptDrops(True) 
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#1e1e1e")) 

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#858585")) 
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if fp.endswith(('.py', '.txt', '.json', '.html', '.css', '.js')):
                self.file_dropped.emit(fp)
                break

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()
        if event.key() == Qt.Key.Key_Tab and not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            prefix = cursor.selectedText()
            if prefix and len(prefix) > 1:
                all_words = set(re.findall(r'\b[a-zA-Z_]\w*\b', self.toPlainText()))
                matches = [w for w in all_words if w.startswith(prefix) and w != prefix]
                if matches:
                    cursor.clearSelection(); cursor.insertText(matches[0][len(prefix):])
                    return 

        if event.key() == Qt.Key.Key_Slash and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            start = cursor.selectionStart(); end = cursor.selectionEnd()
            cursor.setPosition(start); start_block = cursor.blockNumber()
            cursor.setPosition(end); end_block = cursor.blockNumber()
            cursor.beginEditBlock()
            for i in range(start_block, end_block + 1):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                line = cursor.selectedText()
                if line.startswith("# "): cursor.insertText(line[2:])
                else: cursor.insertText("# " + line)
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
            cursor.endEditBlock()
            return
            
        if event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = cursor.selectedText()
            cursor.clearSelection()
            cursor.insertText("\n" + line_text)
            return
            
        super().keyPressEvent(event)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        keyword_format = QTextCharFormat(); keyword_format.setForeground(QColor("#569cd6")); keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = ["def", "class", "return", "if", "elif", "else", "try", "except", "for", "while", "import", "from", "as", "pass", "break", "continue", "in"]
        for word in keywords: self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format))
        string_format = QTextCharFormat(); string_format.setForeground(QColor("#ce9178"))
        self.rules.append((QRegularExpression(r'".*"'), string_format)); self.rules.append((QRegularExpression(r"'.*'"), string_format))
        comment_format = QTextCharFormat(); comment_format.setForeground(QColor("#6a9955"))
        self.rules.append((QRegularExpression(r"#.*"), comment_format))
        func_format = QTextCharFormat(); func_format.setForeground(QColor("#dcdcaa"))
        self.rules.append((QRegularExpression(r"\b[A-Za-z0-9_]+(?=\()"), func_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

# ==============================================================================
# INTERFACE PRINCIPAL DO KYMERA
# ==============================================================================
class KymeraStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kymera Coder 4.19.3 - Editor AI Pro")
        self.resize(1500, 900)
        
        self.client = None
        self.chat_session = None
        self.last_ai_code = ""
        self.current_file = None
        self.has_unsaved_changes = False 
        self.font_size = 14
        
        self.chat_messages = [] # Guarda o histórico da conversa com a IA
        self.settings = QSettings("HydraCorp", "KymeraCoder")
        
        self.init_ui()
        self.setStyleSheet(STYLESHEET)
        self.carregar_memoria()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # TOP BAR
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 5, 10, 5)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("API Key Gemini...")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setMaximumWidth(150) 
        
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.clicked.connect(self.start_discovery)
        
        top_bar.addStretch() 
        top_bar.addWidget(self.token_input)
        top_bar.addWidget(self.btn_connect)
        layout.addLayout(top_bar)

        self.splitter_main = QSplitter(Qt.Orientation.Horizontal)

        # ==========================================
        # COLUNA 1: EXPLORADOR
        # ==========================================
        self.explorer_frame = QFrame(); self.explorer_frame.setObjectName("Explorer")
        self.explorer_frame.setMinimumWidth(200)
        explorer_layout = QVBoxLayout(self.explorer_frame)
        
        explorer_header = QHBoxLayout()
        explorer_header.addWidget(QLabel("EXPLORADOR", objectName="SectionTitle"))
        explorer_header.addStretch()
        
        btn_open_folder = QPushButton("📁")
        btn_open_folder.clicked.connect(self.abrir_pasta)
        explorer_header.addWidget(btn_open_folder)
        explorer_layout.addLayout(explorer_header)

        self.file_system = QFileSystemModel()
        self.file_system.setRootPath(QDir.rootPath())
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_system)
        self.tree_view.setRootIndex(self.file_system.index(os.getcwd()))
        self.tree_view.setHeaderHidden(True)
        for i in range(1, 4): self.tree_view.hideColumn(i)
        self.tree_view.doubleClicked.connect(self.tree_file_clicked)
        explorer_layout.addWidget(self.tree_view)

        # ==========================================
        # COLUNA 2: EDITOR E ABAS DO TERMINAL
        # ==========================================
        self.editor_frame = QFrame(); self.editor_frame.setObjectName("Editor")
        self.editor_frame.setMinimumWidth(500)
        self.editor_splitter = QSplitter(Qt.Orientation.Vertical)
        
        editor_top_widget = QWidget()
        editor_layout = QVBoxLayout(editor_top_widget)
        editor_layout.setContentsMargins(10, 10, 10, 0)
        
        edit_toolbar = QHBoxLayout()
        self.file_label = QLabel("Sem Título-1", objectName="SectionTitle")
        edit_toolbar.addWidget(self.file_label)
        edit_toolbar.addStretch()
        
        btn_salvar = QPushButton("Salvar"); btn_salvar.clicked.connect(self.salvar_arquivo)
        
        self.btn_editor_actions = QPushButton("⚙️ Ações")
        editor_menu = QMenu(self)
        editor_menu.addAction("🔍 Localizar e Substituir", self.abrir_localizar)
        editor_menu.addAction("➡️ Ir para Linha...", self.go_to_line)
        editor_menu.addSeparator()
        editor_menu.addAction("📑 Duplicar Linha (Ctrl+D)", self.duplicate_line)
        editor_menu.addAction("💬 Comentar Bloco (Ctrl+/)", self.toggle_comment)
        editor_menu.addAction("🔄 Alternar Quebra de Linha", self.toggle_wrap)
        editor_menu.addSeparator()
        editor_menu.addAction("☑️ Selecionar Tudo", self.select_all)
        editor_menu.addAction("🗑️ Limpar Editor", self.clear_editor)
        editor_menu.addSeparator()
        editor_menu.addAction("📝 Renomear Arquivo", self.renomear_arquivo)
        editor_menu.addAction("↩ Reverter Arquivo", self.reverter_arquivo)
        self.btn_editor_actions.setMenu(editor_menu)

        self.btn_exe = QPushButton("Compilar .EXE")
        self.btn_exe.clicked.connect(self.gerar_exe)

        self.btn_inject = QPushButton("Inserir")
        self.btn_inject.setObjectName("ToolBtn")
        self.btn_inject.clicked.connect(self.inject_to_editor)

        self.btn_run = QPushButton("▶ Run", objectName="RunBtn")
        self.btn_run.clicked.connect(self.run_code)
        
        edit_toolbar.addWidget(btn_salvar)
        edit_toolbar.addWidget(self.btn_editor_actions)
        edit_toolbar.addWidget(self.btn_exe)
        edit_toolbar.addWidget(self.btn_inject)
        edit_toolbar.addWidget(self.btn_run)
        editor_layout.addLayout(edit_toolbar)

        self.code_editor = SmartCodeEditor()
        self.code_editor.file_dropped.connect(self.abrir_arquivo_direto)
        self.code_editor.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none; font-size: 15px;")
        self.highlighter = PythonHighlighter(self.code_editor.document())
        self.code_editor.textChanged.connect(self.on_text_changed)
        self.code_editor.cursorPositionChanged.connect(self.update_status_bar)
        editor_layout.addWidget(self.code_editor)
        
        # --- ABAS INFERIORES ---
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0,0,0,0)
        bottom_layout.setSpacing(0)

        tabs_header = QHBoxLayout()
        tabs_header.setContentsMargins(10, 0, 10, 0)
        
        self.btn_tab_term = QPushButton("TERMINAL", objectName="ActiveTab"); self.btn_tab_term.setProperty("class", "TabBtn Active")
        self.btn_tab_term.clicked.connect(lambda: self.switch_bottom_tab(0))
        
        self.btn_tab_prob = QPushButton("PROBLEMAS", objectName="InactiveTab"); self.btn_tab_prob.setProperty("class", "TabBtn")
        self.btn_tab_prob.clicked.connect(lambda: self.switch_bottom_tab(1))

        tabs_header.addWidget(self.btn_tab_term)
        tabs_header.addWidget(self.btn_tab_prob)
        tabs_header.addStretch()

        self.btn_debug_ai = QPushButton("Debugar com IA", objectName="ToolBtn")
        self.btn_debug_ai.clicked.connect(self.debug_problems)
        tabs_header.addWidget(self.btn_debug_ai)

        bottom_layout.addLayout(tabs_header)

        self.bottom_stack = QStackedWidget()
        self.terminal = InteractiveTerminal()
        self.terminal.error_ready.connect(self.registrar_problema) 
        self.bottom_stack.addWidget(self.terminal)

        self.problemas_area = QTextEdit()
        self.problemas_area.setReadOnly(True)
        self.problemas_area.setStyleSheet("background: #111111; color: #f14c4c; font-family: Consolas; font-size: 13px; border: none; padding: 10px;")
        self.problemas_area.setText("Nenhum problema detectado no seu espaço de trabalho.")
        self.bottom_stack.addWidget(self.problemas_area)

        bottom_layout.addWidget(self.bottom_stack)
        self.editor_splitter.addWidget(editor_top_widget)
        self.editor_splitter.addWidget(bottom_panel)
        self.editor_splitter.setStretchFactor(0, 3) 
        self.editor_splitter.setStretchFactor(1, 1) 
        
        # ==========================================
        # COLUNA 3: ASSISTENTE I.A. 
        # ==========================================
        self.ai_panel = QFrame(); self.ai_panel.setObjectName("AI_Panel")
        self.ai_panel.setMinimumWidth(300)
        ai_layout = QVBoxLayout(self.ai_panel)
        
        ai_header = QHBoxLayout()
        ai_header.addWidget(QLabel("COPILOT", objectName="SectionTitle"))
        ai_header.addStretch()
        
        self.btn_ai_tools = QPushButton("Ferramentas", objectName="ToolBtn")
        ai_menu = QMenu(self)
        ai_menu.addAction("Achar Bug no Código", self.find_bug)
        ai_menu.addAction("Explicar Código", self.explain_code)
        ai_menu.addAction("Formatar / Limpar", self.format_code)
        ai_menu.addSeparator()
        ai_menu.addAction("Resetar Memória", self.limpar_memoria_ia)
        self.btn_ai_tools.setMenu(ai_menu)
        
        ai_header.addWidget(self.btn_ai_tools)
        ai_layout.addLayout(ai_header)
        
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("border: none; background: transparent; padding: 5px;")
        ai_layout.addWidget(self.chat_area)
        
        chat_input_layout = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Comando (Ex: Crie um script)")
        self.user_input.returnPressed.connect(self.ask_ai)
        
        btn_send_ai = QPushButton("➤", objectName="SendAI")
        btn_send_ai.clicked.connect(self.ask_ai)
        
        chat_input_layout.addWidget(self.user_input)
        chat_input_layout.addWidget(btn_send_ai)
        ai_layout.addLayout(chat_input_layout)

        # MONTAGEM FINAL
        self.splitter_main.addWidget(self.explorer_frame)
        self.splitter_main.addWidget(self.editor_splitter)
        self.splitter_main.addWidget(self.ai_panel)
        
        self.splitter_main.setStretchFactor(0, 1)
        self.splitter_main.setStretchFactor(1, 5)
        self.splitter_main.setStretchFactor(2, 2)
        
        layout.addWidget(self.splitter_main)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_cursor_pos = QLabel("Ln 1, Col 1")
        self.status_bar.addPermanentWidget(self.lbl_cursor_pos)
        self.status_bar.showMessage("Kymera IDE Pronto")

    # --- FUNÇÕES ---
    def switch_bottom_tab(self, index):
        self.bottom_stack.setCurrentIndex(index)
        if index == 0:
            self.btn_tab_term.setStyleSheet("color: #e7e7e7; border-bottom: 2px solid #e7e7e7; background: transparent; padding: 5px 15px; font-weight: bold;")
            self.btn_tab_prob.setStyleSheet("color: #858585; border-bottom: 2px solid transparent; background: transparent; padding: 5px 15px; font-weight: bold;")
        else:
            self.btn_tab_prob.setStyleSheet("color: #e7e7e7; border-bottom: 2px solid #e7e7e7; background: transparent; padding: 5px 15px; font-weight: bold;")
            self.btn_tab_term.setStyleSheet("color: #858585; border-bottom: 2px solid transparent; background: transparent; padding: 5px 15px; font-weight: bold;")

    def registrar_problema(self, msg):
        if "Nenhum problema" in self.problemas_area.toPlainText():
            self.problemas_area.clear()
        self.problemas_area.append(msg)
        self.btn_tab_prob.setStyleSheet("color: #f14c4c; border-bottom: 2px solid #f14c4c; background: transparent; padding: 5px 15px; font-weight: bold;")

    def debug_problems(self):
        erros = self.problemas_area.toPlainText()
        if "Nenhum problema" in erros or not erros: return
        if not self._verificar_motor_ia(): return
        self.switch_bottom_tab(1)
        self.iniciar_transmissao_ia("Conserte os erros que deram no terminal.", f"Analise o meu código e os erros abaixo e me dê a solução em código:\nErros:\n```\n{erros}\n```")

    def abrir_localizar(self): FindReplaceDialog(self.code_editor, self).show()
    
    def go_to_line(self):
        line, ok = QInputDialog.getInt(self, "Ir para Linha", "Número da linha:", 1, 1, self.code_editor.blockCount())
        if ok:
            c = self.code_editor.textCursor(); c.setPosition(0); c.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line - 1)
            self.code_editor.setTextCursor(c); self.code_editor.setFocus()

    def duplicate_line(self):
        c = self.code_editor.textCursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfLine); c.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        t = c.selectedText(); c.clearSelection(); c.insertText("\n" + t)

    def toggle_comment(self):
        c = self.code_editor.textCursor()
        s = c.selectionStart(); e = c.selectionEnd()
        c.setPosition(s); sb = c.blockNumber(); c.setPosition(e); eb = c.blockNumber()
        c.beginEditBlock()
        for i in range(sb, eb + 1):
            c.movePosition(QTextCursor.MoveOperation.StartOfLine); c.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            l = c.selectedText()
            if l.startswith("# "): c.insertText(l[2:])
            else: c.insertText("# " + l)
            c.movePosition(QTextCursor.MoveOperation.NextBlock)
        c.endEditBlock()

    def select_all(self): self.code_editor.selectAll()
    def clear_editor(self): self.code_editor.clear()
    
    def reverter_arquivo(self):
        if not self.current_file: return
        resp = QMessageBox.question(self, "Reverter", "Isso apagará todas as mudanças não salvas. Continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes: self.abrir_arquivo_direto(self.current_file)
            
    def renomear_arquivo(self):
        if not self.current_file: return
        dir_name = os.path.dirname(self.current_file)
        old_name = os.path.basename(self.current_file)
        new_name, ok = QInputDialog.getText(self, "Renomear", "Novo nome:", QLineEdit.EchoMode.Normal, old_name)
        if ok and new_name:
            novo_caminho = os.path.join(dir_name, new_name)
            os.rename(self.current_file, novo_caminho)
            self.current_file = novo_caminho
            self.file_label.setText(new_name)

    def toggle_wrap(self):
        if self.code_editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap:
            self.code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.status_bar.showMessage("Wrap: ATIVADO", 3000)
        else:
            self.code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.status_bar.showMessage("Wrap: DESATIVADO", 3000)

    def _verificar_motor_ia(self):
        if not self.chat_session:
            QMessageBox.warning(self, "Aviso", "Conecte a API Key no topo.")
            return False
        return True

    def carregar_memoria(self):
        t = self.settings.value("gemini_token", "")
        if t: self.token_input.setText(t); self.start_discovery() 
        c = self.settings.value("last_code", "")
        if c: self.code_editor.setPlainText(c); self.has_unsaved_changes = False
        ch = self.settings.value("last_chat", "")
        if ch:
            try:
                self.chat_messages = json.loads(ch)
                self.render_chat()
            except:
                self.chat_messages = []

    def on_text_changed(self): self.has_unsaved_changes = True

    def update_status_bar(self):
        cursor = self.code_editor.textCursor()
        self.lbl_cursor_pos.setText(f"Ln {cursor.blockNumber() + 1}, Col {cursor.columnNumber() + 1}")

    def closeEvent(self, event):
        if self.has_unsaved_changes:
            resp = QMessageBox.question(self, "Aviso", "Você tem código não salvo. Deseja sair?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.No: event.ignore(); return
        self.settings.setValue("gemini_token", self.token_input.text().strip())
        self.settings.setValue("last_code", self.code_editor.toPlainText())
        self.settings.setValue("last_chat", json.dumps(self.chat_messages))
        super().closeEvent(event)

    def abrir_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if pasta:
            self.tree_view.setRootIndex(self.file_system.index(pasta))
            self.terminal.update_dir(pasta) 

    def tree_file_clicked(self, index):
        c = self.file_system.filePath(index)
        if os.path.isfile(c): self.abrir_arquivo_direto(c)

    def abrir_arquivo_direto(self, caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f: self.code_editor.setPlainText(f.read())
            self.current_file = caminho; self.file_label.setText(os.path.basename(caminho)); self.has_unsaved_changes = False
        except: pass

    def salvar_arquivo(self):
        code = self.code_editor.toPlainText()
        if not self.current_file:
            c, _ = QFileDialog.getSaveFileName(self, "Salvar", "main.py", "Python Files (*.py)")
            if not c: return
            self.current_file = c
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f: f.write(code)
            self.file_label.setText(os.path.basename(self.current_file)); self.has_unsaved_changes = False; self.status_bar.showMessage("Salvo", 3000)
        except: pass

    # ==================================================================
    # NOVA IA (RENDERIZADOR EM CARDS / MARKDOWN)
    # ==================================================================
    def start_discovery(self):
        key = self.token_input.text().strip()
        if not key: return
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Conectando...")
        self.worker_disc = DiscoveryWorker(key)
        self.worker_disc.finished.connect(self.on_disc_success)
        self.worker_disc.error.connect(self.on_disc_error)
        self.worker_disc.start()

    def on_disc_success(self, client, chat_session):
        self.client = client; self.chat_session = chat_session
        self.btn_connect.setText("Online"); self.btn_connect.setEnabled(True)

    def on_disc_error(self, err):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("Conectar")
        QMessageBox.critical(self, "Erro", f"Falha de API:\n{err}")

    def limpar_memoria_ia(self):
        if not self._verificar_motor_ia(): return
        self.chat_session = self.client.chats.create(model="gemini-2.5-flash")
        self.chat_messages = []
        self.render_chat() 

    def find_bug(self):
        if not self._verificar_motor_ia(): return
        c = self.code_editor.toPlainText().strip()
        if not c: return
        self.iniciar_transmissao_ia("Ache o erro no código.", f"Encontre bugs e retorne o código corrigido:\n```python\n{c}\n```")

    def explain_code(self):
        if not self._verificar_motor_ia(): return
        c = self.code_editor.toPlainText().strip()
        if not c: return
        self.iniciar_transmissao_ia("Explique o código.", f"Explique o que este código faz:\n```python\n{c}\n```")

    def format_code(self):
        if not self._verificar_motor_ia(): return
        c = self.code_editor.toPlainText().strip()
        if not c: return
        self.iniciar_transmissao_ia("Otimize o código.", f"Formate (PEP8) e limpe código inútil. Retorne apenas o código:\n```python\n{c}\n```")

    def ask_ai(self):
        u = self.user_input.text().strip()
        if not u: return
        if not self._verificar_motor_ia(): return
        
        c = self.code_editor.toPlainText().strip()
        sp = "\n(Instrução interna: Atue como Engenheiro de Software. Use Python. Para GUIs, use PyQt6 Dark Mode. NÃO USE input(). Mande o código em markdown python.)"
        p = f"Dado o código atual, responda: {u}\n\n```python\n{c}\n``` {sp}" if c else u + sp
        self.user_input.clear()
        self.iniciar_transmissao_ia(u, p)

    # FUNÇÃO MÁGICA: Pinta o código em tabelas e formata o texto da I.A.
    def format_markdown(self, text):
        parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
        formatted = []
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                code_content = part.strip("`")
                if "\n" in code_content:
                    lang, code = code_content.split("\n", 1)
                else:
                    lang, code = "", code_content
                
                # HTML Nativo Inquebrável para Cartões de Código!
                code_escaped = html.escape(code.strip())
                card = f"""
                <br><table width="100%" style="background-color: #0A0A0C; border: 1px solid #3c3c3c; border-radius: 4px;">
                    <tr><td style="background-color: #1e1e1e; color: #858585; padding: 4px 8px; font-size: 11px; font-weight: bold; border-bottom: 1px solid #3c3c3c;">&lt;/&gt; CÓDIGO {lang.upper()}</td></tr>
                    <tr><td style="padding: 10px; color: #10b981; font-family: Consolas;">
                        <pre style="margin: 0; font-family: Consolas; font-size: 14px;">{code_escaped}</pre>
                    </td></tr>
                </table><br>
                """
                formatted.append(card)
            else:
                text_html = html.escape(part).replace("\n", "<br>")
                text_html = re.sub(r"\*\*(.*?)\*\*", r"<b style='color:#ffffff;'>\1</b>", text_html)
                formatted.append(text_html)
        return "".join(formatted)

    def render_chat(self):
        html_content = "<div style='font-family: Segoe UI, sans-serif; font-size: 13px; line-height: 1.5; color: #cccccc;'>"
        for msg in self.chat_messages:
            if msg["role"] == "user":
                html_content += f"<div style='margin-bottom: 15px;'><b style='color:#0ea5e9;'>VOCÊ:</b><br>{html.escape(msg['text'])}</div>"
            elif msg["role"] == "ai":
                html_content += f"<div style='margin-bottom: 20px;'><b style='color:#a855f7;'>COPILOT:</b><br>{self.format_markdown(msg['text'])}</div>"
            elif msg["role"] == "error":
                html_content += f"<div style='margin-bottom: 15px; color:#da373c;'><b>ERRO:</b> {html.escape(msg['text'])}</div>"
        html_content += "</div>"
        
        sb = self.chat_area.verticalScrollBar()
        at_bottom = sb.value() == sb.maximum()
        self.chat_area.setHtml(html_content)
        if at_bottom: sb.setValue(sb.maximum())

    def iniciar_transmissao_ia(self, texto_display, prompt_real):
        self.chat_messages.append({"role": "user", "text": texto_display})
        self.chat_messages.append({"role": "ai", "text": ""}) 
        self.render_chat()

        self.worker_ai = AIStreamWorker(self.chat_session, prompt_real)
        self.worker_ai.chunk_received.connect(self.update_chat_typing)
        self.worker_ai.finished.connect(self.on_ai_finished)
        self.worker_ai.error.connect(lambda e: (self.chat_messages.append({"role": "error", "text": e}), self.render_chat()))
        self.worker_ai.start()

    def update_chat_typing(self, chunk):
        if self.chat_messages:
            self.chat_messages[-1]["text"] += chunk
            self.render_chat()

    def on_ai_finished(self, full_text):
        match = re.search(r"```[pP]ython\n(.*?)```", full_text, re.DOTALL)
        if not match: match = re.search(r"```(.*?)```", full_text, re.DOTALL)
        if match: 
            self.last_ai_code = match.group(1).strip()
        else:
            self.last_ai_code = ""

    def inject_to_editor(self):
        if self.last_ai_code:
            c = self.code_editor.textCursor()
            c.insertText("\n" + self.last_ai_code + "\n")
            self.code_editor.setFocus()

    def run_code(self):
        c = self.code_editor.toPlainText().strip()
        if not c: return
        f = self.current_file
        if not f:
            f = os.path.abspath("kymera_temp_run.py")
            with open(f, "w", encoding="utf-8") as file: file.write(c)
        else:
            self.salvar_arquivo()
        self.switch_bottom_tab(0)
        self.terminal.clear_terminal()
        self.terminal.appendPlainText(f"\n> Rodando: {os.path.basename(f)}\n")
        comando = f'{sys.executable} "{f}"'
        self.terminal.executar_comando_direto(comando)

    def gerar_exe(self):
        try: import PyInstaller
        except ImportError:
            QMessageBox.critical(self, "Falta o PyInstaller", "Digite 'pip install pyinstaller' no terminal e dê Enter.")
            return
        c = self.code_editor.toPlainText().strip()
        if not c: return
        r = QMessageBox.question(self, "Ícone", "Adicionar logotipo (.ico)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        i = None
        if r == QMessageBox.StandardButton.Yes:
            i, _ = QFileDialog.getOpenFileName(self, "Selecione o .ico", "", "Icon Files (*.ico)")
        n, _ = QFileDialog.getSaveFileName(self, "Salvar EXE", "meu_app.exe", "Executáveis (*.exe)")
        if not n: return
        d = os.path.dirname(n)
        t = os.path.join(d, "kymera_temp_build.py")
        with open(t, "w", encoding="utf-8") as f: f.write(c)
        
        self.switch_bottom_tab(0)
        self.terminal.append_output(f"\n[COMPILADOR]: Construindo {os.path.basename(n)}...\n")
        self.worker_build = ExeBuilderWorker(t, i)
        self.worker_build.output_ready.connect(lambda txt: self.terminal.append_output(txt + "\n"))
        self.worker_build.finished.connect(lambda s: self.on_exe_finished(s, t, n))
        self.worker_build.start()

    def on_exe_finished(self, success, temp_file, nome_final):
        if success:
            import shutil
            d = os.path.dirname(temp_file)
            ns = os.path.splitext(os.path.basename(temp_file))[0]
            eg = os.path.join(d, "dist", f"{ns}.exe")
            if os.path.exists(eg):
                if os.path.exists(nome_final): os.remove(nome_final) 
                shutil.move(eg, nome_final) 
                self.terminal.append_output(f"\n[SUCESSO]: Salvo em: {nome_final}\n")
                QMessageBox.information(self, "Sucesso", "Executável gerado!")
        else:
            self.registrar_problema("[ERRO DE COMPILAÇÃO]: Verifique os logs no Terminal.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KymeraStudio()
    window.show()
    sys.exit(app.exec())
