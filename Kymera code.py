import sys
import os
import subprocess
import threading
import re
from google import genai
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QPlainTextEdit, QPushButton, 
                             QLineEdit, QLabel, QSplitter, QFileDialog, QFrame, QMessageBox,
                             QStatusBar, QDialog, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression, QSettings, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QSyntaxHighlighter, QTextCharFormat, QColor, QIcon, QKeyEvent

# ==============================================================================
# ESTILO DARK HYDRA PRO (Com novos botões)
# ==============================================================================
STYLESHEET = """
    QMainWindow { background-color: #050505; }
    QWidget { color: #E0E0E0; font-family: 'Inter', 'Segoe UI'; }
    QFrame#Sidebar { background-color: #080808; border-right: 1px solid #1A1A1A; }
    QLineEdit, QTextEdit, QPlainTextEdit { 
        background-color: #0A0A0C; border: 1px solid #1e293b; 
        border-radius: 6px; padding: 12px; color: #f8fafc;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #a855f7; }
    QPushButton { 
        background-color: #151515; border: 1px solid #333; 
        border-radius: 6px; padding: 10px 15px; font-weight: bold; transition: 0.2s; color: #E0E0E0;
    }
    QPushButton:hover { background-color: #1A1A1A; border: 1px solid #a855f7; }
    
    QPushButton#RunBtn { color: #10b981; border: 1px solid #059669; background: rgba(16,185,129,0.1); }
    QPushButton#RunBtn:hover { background: rgba(16,185,129,0.2); }
    QPushButton#ExeBtn { color: #0ea5e9; border: 1px solid #0284c7; background: rgba(14,165,233,0.1); }
    QPushButton#ExeBtn:hover { background: rgba(14,165,233,0.2); }
    QPushButton#InjectBtn { color: #a855f7; border: 1px solid #9333ea; background: rgba(168,85,247,0.1); }
    QPushButton#InjectBtn:hover { background: rgba(168,85,247,0.2); }
    
    QPushButton#ToolBtn { color: #f59e0b; border: 1px solid #d97706; background: rgba(245,158,11,0.05); font-size: 11px; padding: 8px; }
    QPushButton#ToolBtn:hover { background: rgba(245,158,11,0.2); }
    QPushButton#FormatBtn { color: #3b82f6; border: 1px solid #2563eb; background: rgba(59,130,246,0.05); font-size: 11px; padding: 8px; }
    QPushButton#FormatBtn:hover { background: rgba(59,130,246,0.2); }
    QPushButton#SmallBtn { padding: 8px; font-size: 12px; }

    QLabel#Title { color: #64748b; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    QStatusBar { background: #080808; color: #64748b; font-family: monospace; border-top: 1px solid #1A1A1A; }
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
        self.setStyleSheet(STYLESHEET + "QDialog { background-color: #0F0F0F; border: 1px solid #333; }")
        
        layout = QVBoxLayout(self)
        
        self.input_find = QLineEdit()
        self.input_find.setPlaceholderText("Localizar...")
        layout.addWidget(self.input_find)
        
        self.input_replace = QLineEdit()
        self.input_replace.setPlaceholderText("Substituir por...")
        layout.addWidget(self.input_replace)
        
        btn_layout = QHBoxLayout()
        btn_find = QPushButton("Localizar Próximo")
        btn_find.clicked.connect(self.find_next)
        btn_replace = QPushButton("Substituir")
        btn_replace.clicked.connect(self.replace)
        btn_replace_all = QPushButton("Substituir Tudo")
        btn_replace_all.clicked.connect(self.replace_all)
        
        btn_layout.addWidget(btn_find)
        btn_layout.addWidget(btn_replace)
        btn_layout.addWidget(btn_replace_all)
        layout.addLayout(btn_layout)

    def find_next(self):
        text = self.input_find.text()
        if text and not self.editor.find(text):
            self.editor.moveCursor(QTextCursor.MoveOperation.Start)
            self.editor.find(text)

    def replace(self):
        if self.editor.textCursor().hasSelection():
            self.editor.textCursor().insertText(self.input_replace.text())
        self.find_next()

    def replace_all(self):
        text_to_find = self.input_find.text()
        text_to_replace = self.input_replace.text()
        if not text_to_find: return
        
        content = self.editor.toPlainText()
        new_content = content.replace(text_to_find, text_to_replace)
        self.editor.setPlainText(new_content)
        self.accept()

# ==============================================================================
# EDITOR INTELIGENTE E HIGHLIGHTER
# ==============================================================================
class SmartCodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 14))
        self.setTabStopDistance(40)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            prefix = cursor.selectedText()
            if prefix and len(prefix) > 1:
                all_words = set(re.findall(r'\b[a-zA-Z_]\w*\b', self.toPlainText()))
                matches = [w for w in all_words if w.startswith(prefix) and w != prefix]
                if matches:
                    completion = matches[0][len(prefix):]
                    cursor.clearSelection()
                    cursor.insertText(completion)
                    return 
        super().keyPressEvent(event)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#56b6c2"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = ["def", "class", "return", "if", "elif", "else", "try", "except", 
                    "for", "while", "import", "from", "as", "pass", "break", "continue", "in"]
        for word in keywords: self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format))
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#a3be8c"))
        self.rules.append((QRegularExpression(r'".*"'), string_format))
        self.rules.append((QRegularExpression(r"'.*'"), string_format))
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#5c6370"))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#.*"), comment_format))
        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#e5c07b"))
        self.rules.append((QRegularExpression(r"\b[A-Za-z0-9_]+(?=\()"), func_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

# ==============================================================================
# WORKERS
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

class TerminalWorker(QThread):
    output_ready = pyqtSignal(str)
    error_ready = pyqtSignal(str)
    def __init__(self, command_list, is_file=True):
        super().__init__()
        self.command_list = command_list
        self.is_file = is_file
    def run(self):
        try:
            if self.is_file:
                # Executa script isolado
                file_path = self.command_list[0]
                work_dir = os.path.dirname(os.path.abspath(file_path)) if file_path else os.getcwd()
                if sys.platform == "win32":
                    comando = f'start cmd /k "{sys.executable}" "{file_path}"'
                    subprocess.Popen(comando, shell=True, cwd=work_dir)

                else:
                    subprocess.Popen(["x-terminal-emulator", "-e", f"{sys.executable} {file_path}"], cwd=work_dir)
                self.output_ready.emit(f"> Execução isolada iniciada.")
            else:
                # Executa comandos no terminal da IDE (ex: pip install)
                process = subprocess.Popen(self.command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                for line in process.stdout: self.output_ready.emit(line.strip())
                for line in process.stderr: self.error_ready.emit(line.strip())
        except Exception as e:
            self.error_ready.emit(f"Erro crítico: {str(e)}")

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
            self.output_ready.emit(f"Erro ao Compilar: {str(e)}")
            self.finished.emit(False)

# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================
class KymeraStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kymera Coder v4.14 - Ultimate Edition")
        self.resize(1400, 900)
        
        self.client = None
        self.chat_session = None
        self.last_ai_code = ""
        self.current_file = None
        self.has_unsaved_changes = False 
        
        self.settings = QSettings("HydraCorp", "KymeraCoder")
        self.font_size = 14
        
        self.init_ui()
        self.setStyleSheet(STYLESHEET)
        self.carregar_memoria()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # TOP BAR DE FERRAMENTAS
        top_bar = QHBoxLayout()
        btn_abrir = QPushButton("📂 Abrir"); btn_abrir.clicked.connect(self.abrir_arquivo)
        btn_salvar = QPushButton("💾 Salvar"); btn_salvar.clicked.connect(self.salvar_arquivo)
        
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("COLE SEU TOKEN DO GEMINI AQUI E PRESSIONE CONECTAR...")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.btn_connect = QPushButton("⚡ CONECTAR / TROCAR MOTOR")
        self.btn_connect.clicked.connect(self.start_discovery)
        
        top_bar.addWidget(btn_abrir); top_bar.addWidget(btn_salvar)
        top_bar.addWidget(self.token_input); top_bar.addWidget(self.btn_connect)
        layout.addLayout(top_bar)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # ==========================================
        # ESQUERDA: CHAT E FERRAMENTAS DE I.A.
        # ==========================================
        self.sidebar = QFrame(); self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        chat_header = QHBoxLayout()
        chat_header.addWidget(QLabel("🧠 ASSISTENTE KYMERA", objectName="Title"))
        chat_header.addStretch()
        btn_clear_chat = QPushButton("Limpar Memória")
        btn_clear_chat.clicked.connect(self.limpar_memoria_ia)
        btn_clear_chat.setStyleSheet("padding: 2px 10px; font-size: 10px;")
        chat_header.addWidget(btn_clear_chat)
        sidebar_layout.addLayout(chat_header)
        
        # GRID DE BOTÕES PROFISSIONAIS (AGORA 3x2)
        tools_grid = QGridLayout()
        
        self.btn_bug = QPushButton("🔍 ACHAR BUG", objectName="ToolBtn")
        self.btn_bug.clicked.connect(self.find_bug)
        tools_grid.addWidget(self.btn_bug, 0, 0)
        
        self.btn_explain = QPushButton("📝 EXPLICAR CÓDIGO", objectName="ToolBtn")
        self.btn_explain.clicked.connect(self.explain_code)
        tools_grid.addWidget(self.btn_explain, 0, 1)

        self.btn_format = QPushButton("🧹 FORMATAR CÓDIGO", objectName="FormatBtn")
        self.btn_format.clicked.connect(self.format_code)
        tools_grid.addWidget(self.btn_format, 1, 0)

        self.btn_clean = QPushButton("🗑️ LIMPAR LIXO", objectName="FormatBtn")
        self.btn_clean.setToolTip("A IA removerá prints esquecidos e variáveis não usadas.")
        self.btn_clean.clicked.connect(self.clean_code)
        tools_grid.addWidget(self.btn_clean, 1, 1)

        self.btn_docstring = QPushButton("📚 GERAR DOCSTRINGS", objectName="ToolBtn")
        self.btn_docstring.setToolTip("A IA documentará todas as funções como um dev profissional.")
        self.btn_docstring.clicked.connect(self.generate_docstrings)
        tools_grid.addWidget(self.btn_docstring, 2, 0, 1, 2)

        sidebar_layout.addLayout(tools_grid)
        
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("font-size: 13px; line-height: 1.5;")
        sidebar_layout.addWidget(self.chat_area)
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Comande a I.A... (Ex: Crie um App de Relógio em PyQt6)")
        self.user_input.returnPressed.connect(self.ask_ai)
        sidebar_layout.addWidget(self.user_input)

        # ==========================================
        # CENTRO: EDITOR E COMPILADOR
        # ==========================================
        self.editor_container = QFrame()
        editor_layout = QVBoxLayout(self.editor_container)
        
        edit_toolbar = QHBoxLayout()
        self.file_label = QLabel("📝 NOVO ARQUIVO (Não Salvo)", objectName="Title")
        edit_toolbar.addWidget(self.file_label)
        
        # Ferramentas do Editor
        btn_zoom_out = QPushButton("A-", objectName="SmallBtn")
        btn_zoom_out.clicked.connect(lambda: self.mudar_zoom(-1))
        btn_zoom_in = QPushButton("A+", objectName="SmallBtn")
        btn_zoom_in.clicked.connect(lambda: self.mudar_zoom(1))
        
        btn_find = QPushButton("🔍 Localizar", objectName="SmallBtn")
        btn_find.clicked.connect(self.abrir_localizar)

        btn_pip = QPushButton("📦 Instalar Bibliotecas (Pip)", objectName="SmallBtn")
        btn_pip.setStyleSheet("color: #10b981; border: 1px solid #10b981;")
        btn_pip.clicked.connect(self.auto_install_pip)

        edit_toolbar.addWidget(btn_zoom_out)
        edit_toolbar.addWidget(btn_zoom_in)
        edit_toolbar.addWidget(btn_find)
        edit_toolbar.addWidget(btn_pip)
        edit_toolbar.addStretch()
        
        self.btn_undo = QPushButton("↩ DESFAZER", objectName="FormatBtn")
        self.btn_undo.clicked.connect(self.desfazer_codigo)
        
        self.btn_inject = QPushButton("📥 INSERIR NO CURSOR", objectName="InjectBtn")
        self.btn_inject.clicked.connect(self.inject_to_editor)
        
        self.btn_exe = QPushButton("📦 GERAR .EXE COM ÍCONE", objectName="ExeBtn")
        self.btn_exe.clicked.connect(self.gerar_exe)

        self.btn_run = QPushButton("▶ EXECUTAR CÓDIGO", objectName="RunBtn")
        self.btn_run.clicked.connect(self.run_code)
        
        edit_toolbar.addWidget(self.btn_undo)
        edit_toolbar.addWidget(self.btn_inject)
        edit_toolbar.addWidget(self.btn_exe)
        edit_toolbar.addWidget(self.btn_run)
        editor_layout.addLayout(edit_toolbar)

        self.code_editor = SmartCodeEditor()
        self.code_editor.setFont(QFont("Consolas", self.font_size))
        self.highlighter = PythonHighlighter(self.code_editor.document())
        self.code_editor.textChanged.connect(self.on_text_changed)
        self.code_editor.cursorPositionChanged.connect(self.update_status_bar)
        editor_layout.addWidget(self.code_editor)

        # ==========================================
        # TERMINAL DE STATUS
        # ==========================================
        term_header = QHBoxLayout()
        term_header.addWidget(QLabel("💻 STATUS DO COMPILADOR", objectName="Title"))
        term_header.addStretch()
        btn_clear_term = QPushButton("Limpar Log")
        btn_clear_term.clicked.connect(lambda: self.terminal.clear())
        btn_clear_term.setStyleSheet("padding: 2px 10px; font-size: 10px;")
        term_header.addWidget(btn_clear_term)
        editor_layout.addLayout(term_header)

        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFixedHeight(120)
        self.terminal.setStyleSheet("background: #000; color: #10b981; font-family: Consolas; font-size: 13px; border: 1px solid #1e293b;")
        editor_layout.addWidget(self.terminal)

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.editor_container)
        self.splitter.setStretchFactor(1, 4)
        layout.addWidget(self.splitter)
        
        # Barra Inferior
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_cursor_pos = QLabel("Linha 1, Coluna 1")
        self.status_bar.addPermanentWidget(self.lbl_cursor_pos)
        self.status_bar.showMessage("Kymera Studio Pronto.")

    # --- LÓGICA DE PROTEÇÃO E SISTEMA ---

    def _verificar_motor_ia(self):
        if not self.chat_session:
            QMessageBox.warning(self, "Motor Desconectado", "⚠️ Cole o seu Token do Gemini na barra superior e clique em 'CONECTAR MOTOR IA'.")
            return False
        return True

    def carregar_memoria(self):
        token_salvo = self.settings.value("gemini_token", "")
        if token_salvo:
            self.token_input.setText(token_salvo)
            self.start_discovery() 
            
        codigo_salvo = self.settings.value("last_code", "")
        if codigo_salvo:
            self.code_editor.setPlainText(codigo_salvo)
            self.has_unsaved_changes = False
            
        chat_salvo = self.settings.value("last_chat", "")
        if chat_salvo:
            self.chat_area.setHtml(chat_salvo)

    def on_text_changed(self):
        self.has_unsaved_changes = True

    def update_status_bar(self):
        cursor = self.code_editor.textCursor()
        linha = cursor.blockNumber() + 1
        coluna = cursor.columnNumber() + 1
        self.lbl_cursor_pos.setText(f"Linha {linha}, Coluna {coluna}")

    def closeEvent(self, event):
        if self.has_unsaved_changes:
            resp = QMessageBox.question(self, "Alterações não salvas", "Você tem código não salvo. Deseja sair mesmo assim?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self.settings.setValue("gemini_token", self.token_input.text().strip())
        self.settings.setValue("last_code", self.code_editor.toPlainText())
        self.settings.setValue("last_chat", self.chat_area.toHtml())
        super().closeEvent(event)

    def mudar_zoom(self, delta):
        self.font_size = max(8, min(30, self.font_size + delta))
        self.code_editor.setFont(QFont("Consolas", self.font_size))

    def abrir_localizar(self):
        dialog = FindReplaceDialog(self.code_editor, self)
        dialog.show()

    def auto_install_pip(self):
        """Lê os imports do código e instala no Windows via CMD"""
        codigo = self.code_editor.toPlainText()
        imports_encontrados = re.findall(r'^(?:import|from)\s+([a-zA-Z0-9_]+)', codigo, re.MULTILINE)
        
        libs_padrao = {"sys", "os", "re", "math", "time", "datetime", "json", "random", "subprocess", "threading"}
        libs_para_instalar = list(set(imports_encontrados) - libs_padrao)
        
        if not libs_para_instalar:
            QMessageBox.information(self, "Pip", "Nenhuma biblioteca externa encontrada para instalar.")
            return
            
        resp = QMessageBox.question(self, "Instalar Dependências", f"O Kymera encontrou estas bibliotecas:\n{', '.join(libs_para_instalar)}\n\nDeseja tentar instalar todas via PIP agora?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if resp == QMessageBox.StandardButton.Yes:
            self.terminal.clear()
            self.terminal.append(f"<b style='color:#0ea5e9;'>[PIP] Instalando: {', '.join(libs_para_instalar)}...</b><br>")
            # Chama o TerminalWorker passando a lista do pip
            comando = [sys.executable, "-m", "pip", "install"] + libs_para_instalar
            self.worker_pip = TerminalWorker(comando, is_file=False)
            self.worker_pip.output_ready.connect(lambda t: self.terminal.append(t))
            self.worker_pip.error_ready.connect(lambda t: self.terminal.append(f"<span style='color:#f59e0b;'>{t}</span>"))
            self.worker_pip.start()

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir Código", "", "Python Files (*.py);;All Files (*)")
        if caminho:
            with open(caminho, 'r', encoding='utf-8') as f: self.code_editor.setPlainText(f.read())
            self.current_file = caminho
            self.file_label.setText(f"📝 {os.path.basename(caminho)}")
            self.has_unsaved_changes = False

    def salvar_arquivo(self):
        code = self.code_editor.toPlainText()
        if not self.current_file:
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar Código", "meu_app.py", "Python Files (*.py)")
            if not caminho: return
            self.current_file = caminho
        with open(self.current_file, 'w', encoding='utf-8') as f: f.write(code)
        self.file_label.setText(f"📝 {os.path.basename(self.current_file)}")
        self.has_unsaved_changes = False
        self.status_bar.showMessage("Arquivo salvo.", 3000)

    def desfazer_codigo(self):
        self.code_editor.undo()
        self.terminal.append("<i style='color:#f59e0b;'>Ação desfeita. O código retornou ao estado anterior.</i>")

    def start_discovery(self):
        key = self.token_input.text().strip()
        if not key: return
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("⏳ CONECTANDO...")
        self.worker_disc = DiscoveryWorker(key)
        self.worker_disc.finished.connect(self.on_disc_success)
        self.worker_disc.error.connect(self.on_disc_error)
        self.worker_disc.start()

    def on_disc_success(self, client, chat_session):
        self.client = client
        self.chat_session = chat_session
        self.chat_area.append("<b style='color:#a855f7;'>[SISTEMA]:</b> Motor Neural Conectado/Atualizado com sucesso.")
        self.btn_connect.setText("MOTOR ONLINE")
        self.btn_connect.setStyleSheet("color: #10b981; border-color: #10b981;")
        self.btn_connect.setEnabled(True)

    def on_disc_error(self, err):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("⚡ CONECTAR MOTOR IA")
        QMessageBox.critical(self, "Erro", f"Falha na conexão com o Gemini:\n{err}")

    def limpar_memoria_ia(self):
        if not self._verificar_motor_ia(): return
        self.chat_session = self.client.chats.create(model="gemini-2.5-flash")
        self.chat_area.clear() 
        self.chat_area.append("<b style='color:#da373c;'>[SISTEMA]:</b> Memória da I.A. limpa. Novo projeto iniciado.<br>")

    # --- FUNÇÕES DAS FERRAMENTAS PROFISSIONAIS ---
    def find_bug(self):
        if not self._verificar_motor_ia(): return
        codigo = self.code_editor.toPlainText().strip()
        if not codigo: return
        self.iniciar_transmissao_ia("Encontre o erro neste código.", f"Analise, encontre bugs e me mande o código corrigido:\n```python\n{codigo}\n```", "#f59e0b")

    def explain_code(self):
        if not self._verificar_motor_ia(): return
        codigo = self.code_editor.toPlainText().strip()
        if not codigo: return
        self.iniciar_transmissao_ia("Me explique o que este código faz.", f"Explique de forma detalhada o que este código faz para um iniciante:\n```python\n{codigo}\n```", "#3b82f6")

    def format_code(self):
        if not self._verificar_motor_ia(): return
        codigo = self.code_editor.toPlainText().strip()
        if not codigo: return
        self.iniciar_transmissao_ia("Otimize e formate meu código.", f"Formate (PEP8) e otimize a velocidade deste código. Mande apenas o código final:\n```python\n{codigo}\n```", "#10b981")

    def clean_code(self):
        if not self._verificar_motor_ia(): return
        codigo = self.code_editor.toPlainText().strip()
        if not codigo: return
        self.iniciar_transmissao_ia("Limpe o lixo do meu código.", f"Remova funções vazias, imports não utilizados e 'prints' desnecessários deste código. Me mande a versão final limpa:\n```python\n{codigo}\n```", "#ef4444")

    def generate_docstrings(self):
        if not self._verificar_motor_ia(): return
        codigo = self.code_editor.toPlainText().strip()
        if not codigo: return
        self.iniciar_transmissao_ia("Crie a documentação deste código.", f"Adicione Docstrings profissionais e comentários explicativos em todas as classes e funções deste código. Retorne apenas o código comentado:\n```python\n{codigo}\n```", "#a855f7")

    def ask_ai(self):
        user_text = self.user_input.text().strip()
        if not user_text: return
        if not self._verificar_motor_ia(): return
        
        codigo_atual = self.code_editor.toPlainText().strip()
        system_prompt = "\n(Instrução interna: Crie APENAS interfaces gráficas com PyQt6 ou Tkinter. NUNCA crie programas com 'input()'. Retorne o código em markdown python.)"
        prompt_inteligente = f"Dado o código atual abaixo, responda: {user_text}\n\n```python\n{codigo_atual}\n``` {system_prompt}" if codigo_atual else user_text + system_prompt
        
        self.user_input.clear()
        self.iniciar_transmissao_ia(user_text, prompt_inteligente, color="#94a3b8")

    def iniciar_transmissao_ia(self, texto_display, prompt_real, color):
        self.chat_area.append(f"<br><b style='color:{color};'>VOCÊ:</b> {texto_display}<br>")
        self.chat_area.append(f"<b style='color:#a855f7;'>KYMERA:</b> ")
        self.worker_ai = AIStreamWorker(self.chat_session, prompt_real)
        self.worker_ai.chunk_received.connect(self.update_chat_typing)
        self.worker_ai.finished.connect(self.on_ai_finished)
        self.worker_ai.error.connect(lambda e: self.chat_area.append(f"<br><b style='color:#da373c;'>{e}</b>"))
        self.worker_ai.start()

    def update_chat_typing(self, chunk):
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(chunk.replace("\n", "<br>").replace("`", ""))
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()

    def on_ai_finished(self, full_text):
        match = re.search(r"```[pP]ython\n(.*?)```", full_text, re.DOTALL)
        if not match: match = re.search(r"```(.*?)```", full_text, re.DOTALL)
        if match: 
            self.last_ai_code = match.group(1).strip()
            self.chat_area.append("<br><br><i style='color:#10b981;'>[Código pronto. Pressione 📥 INSERIR NO CURSOR]</i>")
        else:
            self.last_ai_code = ""

    def inject_to_editor(self):
        if self.last_ai_code:
            cursor = self.code_editor.textCursor()
            cursor.insertText("\n" + self.last_ai_code + "\n")
            self.code_editor.setFocus()

    def run_code(self):
        code = self.code_editor.toPlainText().strip()
        if not code: return
        self.terminal.clear()
        self.terminal.append("<i style='color:#64748b;'>Lançando ambiente isolado...</i><br>")
        
        file_to_run = self.current_file
        if not file_to_run:
            file_to_run = os.path.abspath("kymera_temp_run.py")
            with open(file_to_run, "w", encoding="utf-8") as f: f.write(code)
        else:
            self.salvar_arquivo()
        
        self.worker_term = TerminalWorker([sys.executable, file_to_run], is_file=True)
        self.worker_term.output_ready.connect(lambda t: self.terminal.append(t))
        self.worker_term.error_ready.connect(lambda t: self.terminal.append(f"<span style='color:#da373c;'>{t}</span>"))
        self.worker_term.start()

    def gerar_exe(self):
        try:
            import PyInstaller
        except ImportError:
            QMessageBox.critical(self, "Dependência Ausente", "O compilador precisa do PyInstaller.\nAbra o terminal do Windows e digite:\npip install pyinstaller")
            return

        code = self.code_editor.toPlainText().strip()
        if not code: return

        resposta_icone = QMessageBox.question(self, "Ícone do Programa", "Deseja adicionar um logotipo (.ico) ao seu aplicativo?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        icon_path = None
        if resposta_icone == QMessageBox.StandardButton.Yes:
            icon_path, _ = QFileDialog.getOpenFileName(self, "Selecione o arquivo .ico", "", "Icon Files (*.ico)")
            if not icon_path: return

        nome_exe, _ = QFileDialog.getSaveFileName(self, "Onde salvar o seu .EXE final?", "meu_app.exe", "Executáveis (*.exe)")
        if not nome_exe: return

        self.terminal.clear()
        self.terminal.append(f"<b style='color:#0ea5e9;'>[COMPILADOR]: Iniciando construção. Isso pode levar alguns minutos...</b><br>")
        
        base_dir = os.path.dirname(nome_exe)
        temp_file = os.path.join(base_dir, "kymera_temp_build.py")
        with open(temp_file, "w", encoding="utf-8") as f: f.write(code)

        self.btn_exe.setEnabled(False)
        self.btn_exe.setText("⏳ COMPILANDO...")
        
        self.worker_build = ExeBuilderWorker(temp_file, icon_path)
        self.worker_build.output_ready.connect(lambda t: self.terminal.append(f"<span style='color:#64748b;'>{t}</span>"))
        self.worker_build.finished.connect(lambda success: self.on_exe_finished(success, temp_file, nome_exe))
        self.worker_build.start()

    def on_exe_finished(self, success, temp_file, nome_final):
        self.btn_exe.setEnabled(True)
        self.btn_exe.setText("📦 GERAR .EXE COM ÍCONE")
        
        if success:
            import shutil
            base_dir = os.path.dirname(temp_file)
            nome_sem_py = os.path.splitext(os.path.basename(temp_file))[0]
            exe_gerado = os.path.join(base_dir, "dist", f"{nome_sem_py}.exe")
            if os.path.exists(exe_gerado):
                if os.path.exists(nome_final): os.remove(nome_final) 
                shutil.move(exe_gerado, nome_final) 
                self.terminal.append(f"<br><b style='color:#10b981;'>[SUCESSO]: Aplicativo gerado e salvo em: {nome_final}</b>")
        else:
            self.terminal.append("<br><b style='color:#da373c;'>[FALHA]: O compilador encontrou um erro.</b>")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KymeraStudio()
    window.show()
    sys.exit(app.exec())
