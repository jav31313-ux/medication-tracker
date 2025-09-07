from datetime import datetime, timedelta
import json
import os
import threading
import time
try:
    import winsound  # Para sonidos en Windows
except ImportError:
    winsound = None  # Para Android/otros sistemas

import matplotlib
matplotlib.use('Agg')  # Backend sin GUI para Kivy
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import base64

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
import calendar
from kivy.uix.dropdown import DropDown
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage

Window.size = (420, 720)

USUARIO_FILE = "usuario.json"
MEDICAMENTOS_FILE = "medicamentos.json"
HISTORIAL_FILE = "historial_notificaciones.json"
CHECKLIST_FILE = "checklist_diario.json"


class LoginScreen(Screen):
    pass

    def iniciar_sesion(self):
        nombre = self.ids.nombre_input.text.strip()
        if not nombre:
            self.ids.info_label.text = "[color=#FF0000]Debes ingresar un nombre[/color]"
            return
        with open(USUARIO_FILE, "w", encoding="utf-8") as f:
            json.dump({"nombre": nombre}, f)
        self.manager.current = "main"
        self.manager.get_screen("main").bienvenida()

class MainScreen(Screen):
    medicamentos = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.medicamentos = []
        self.checklist_diario = {}
        self.usuario_actual = ""
        self.load_meds()
        self.load_checklist()
        self.load_usuario()
        self.iniciar_notificaciones_thread = None
        self.dose_reminder_thread = None
        self.notification_thread = None
        self.stop_notifications = False
        self.historial_notificaciones = []
        Clock.schedule_once(lambda dt: self.load_meds_and_setup(), 0)

    def load_meds_and_setup(self):
        self.load_meds()
        self.load_historial()
        self.refresh_list()
        self.start_notification_system()
        self.start_dose_reminders()

    def load_usuario(self):
        """Carga el usuario actual desde el archivo"""
        if os.path.exists(USUARIO_FILE):
            try:
                with open(USUARIO_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.usuario_actual = data.get("nombre", "")
            except Exception:
                self.usuario_actual = ""
        else:
            self.usuario_actual = ""

    def bienvenida(self):
        self.load_usuario()  # Recargar usuario al mostrar bienvenida
        if self.usuario_actual:
            self.ids.bienvenida_label.text = f"¡Hola, {self.usuario_actual}! Aquí está tu lista."
        else:
            self.ids.bienvenida_label.text = "¡Bienvenida/o!"

    def cerrar_sesion(self):
        if os.path.exists(USUARIO_FILE):
            try:
                os.remove(USUARIO_FILE)
            except Exception:
                pass
        self.manager.current = "login"

    # ---------------- persistence ----------------
    def load_meds(self):
        try:
            if os.path.exists(MEDICAMENTOS_FILE):
                with open(MEDICAMENTOS_FILE, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                    self.medicamentos = json.loads(contenido) if contenido else []
            else:
                self.medicamentos = []
        except Exception:
            self.medicamentos = []

    def save_meds(self):
        try:
            with open(MEDICAMENTOS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.medicamentos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando medicamentos: {e}")
    
    def load_checklist(self):
        """Carga el checklist diario"""
        try:
            if os.path.exists(CHECKLIST_FILE):
                with open(CHECKLIST_FILE, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                    data = json.loads(contenido) if contenido else {}
                    
                    # Solo cargar si es del día actual
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    if data.get('fecha') == hoy:
                        self.checklist_diario = data.get('medicamentos', {})
                    else:
                        self.checklist_diario = {}
            else:
                self.checklist_diario = {}
        except Exception as e:
            print(f"Error cargando checklist: {e}")
            self.checklist_diario = {}
    
    def save_checklist(self):
        """Guarda el checklist diario"""
        try:
            hoy = datetime.now().strftime("%Y-%m-%d")
            data = {
                'fecha': hoy,
                'medicamentos': self.checklist_diario
            }
            with open(CHECKLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando checklist: {e}")
    
    # ---------------- historial notificaciones ----------------
    def load_historial(self):
        try:
            if os.path.exists(HISTORIAL_FILE):
                with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                    contenido = f.read().strip()
                    self.historial_notificaciones = json.loads(contenido) if contenido else []
            else:
                self.historial_notificaciones = []
        except Exception:
            self.historial_notificaciones = []

    def save_historial(self):
        try:
            with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
                json.dump(self.historial_notificaciones, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def agregar_al_historial(self, tipo, medicamento, mensaje):
        """Agrega una notificación al historial"""
        notificacion = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": tipo,  # "dosis", "stock_bajo", "agotado"
            "medicamento": medicamento,
            "mensaje": mensaje,
            "leida": False
        }
        self.historial_notificaciones.insert(0, notificacion)  # Más recientes primero
        # Mantener solo las últimas 50 notificaciones
        if len(self.historial_notificaciones) > 50:
            self.historial_notificaciones = self.historial_notificaciones[:50]
        self.save_historial()

    # ---------------- lista UI ----------------
    def refresh_list(self):
        lista = self.ids.lista_medicamentos
        lista.clear_widgets()
        for i, m in enumerate(self.medicamentos):
            # Calcular días restantes
            dias_restantes = "N/A"
            if m.get("fecha_fin"):
                try:
                    fecha_fin = datetime.strptime(m["fecha_fin"], "%Y-%m-%d %H:%M")
                    dias_restantes = (fecha_fin - datetime.now()).days
                    if dias_restantes < 0:
                        dias_restantes = "¡AGOTADO!"
                    else:
                        dias_restantes = f"{dias_restantes} días"
                except:
                    dias_restantes = "Error"
            
            # Color de alerta
            color_texto = "white"
            if isinstance(dias_restantes, str) and "días" in dias_restantes:
                try:
                    dias_num = int(dias_restantes.split()[0])
                    if dias_num <= 3:
                        color_texto = "red"
                except:
                    pass
            
            # Color de fondo según estado
            print(f"DEBUG COLOR: medicamento={m['nombre']}, dias_restantes={dias_restantes}, tipo={type(dias_restantes)}")
            if isinstance(dias_restantes, str) and "días" in dias_restantes:
                try:
                    dias_num = int(dias_restantes.split()[0])
                    print(f"DEBUG COLOR: dias_num={dias_num}")
                    if dias_num <= 3:
                        bg_color = (1, 0.8, 0.8, 1)  # Rojo más intenso para urgente
                        print("DEBUG COLOR: usando rojo")
                    elif dias_num <= 7:
                        bg_color = (1, 0.9, 0.6, 1)  # Amarillo más intenso para advertencia
                        print("DEBUG COLOR: usando amarillo")
                    else:
                        bg_color = (0.8, 1, 0.8, 1)  # Verde más intenso para normal
                        print("DEBUG COLOR: usando verde")
                except Exception as e:
                    bg_color = (1, 0.7, 0.9, 1)  # Rosado intenso para errores
                    print(f"DEBUG COLOR: error en parsing, usando rosado: {e}")
            else:
                bg_color = (1, 0.6, 0.8, 1)  # ROSADO MUY VISIBLE para sin fecha
                print("DEBUG COLOR: sin fecha, usando rosado intenso")
            
            # Verificar si debe tomarse hoy y si ya se tomó
            debe_tomarse_hoy = self.es_dia_de_toma(m, datetime.now())
            ya_tomado = self.checklist_diario.get(str(i), False)
            
            # Emoji de estado
            estado_emoji = "✅" if ya_tomado else "⏰" if debe_tomarse_hoy else "💊"
            
            # Color de fondo adicional para medicamentos completados
            if ya_tomado and debe_tomarse_hoy:
                bg_color = (0.9, 1, 0.9, 1)  # Verde claro para completado
        
            item = Button(
                text=f"{estado_emoji} {m['nombre']} - {m.get('descripcion', 'Sin descripción')}\n📦 {m['presentacion']} • Cantidad: {m.get('cantidad_actual', m['cantidad_total'])} • Dosis: {m['dosis']}\n⏰ Cada {m['frecuencia_dias']} días | Se acaba en: {dias_restantes}\n{'✅ TOMADO HOY' if ya_tomado and debe_tomarse_hoy else '📋 Pendiente hoy' if debe_tomarse_hoy else ''}",
                size_hint_y=None,
                height=dp(110),
                text_size=(None, None),
                halign='left',
                valign='middle',
                background_color=bg_color,
                color=(0.2, 0.2, 0.2, 1),
                font_size='14sp'
            )
            item.bind(on_release=lambda x, idx=i: self.mostrar_opciones(idx))
            lista.add_widget(item)

    # ---------------- agregar / editar ----------------
    def agregar_medicamento(self):
        nombre = self.ids.m_nombre.text.strip()
        descripcion = self.ids.m_descripcion.text.strip()
        presentacion = self.ids.m_presentacion.text.strip()
        cantidad_text = self.ids.m_cantidad.text.strip()
        dosis_text = self.ids.m_dosis.text.strip()
        frecuencia_text = self.ids.m_frecuencia.text.strip()
        inicio_text = self.ids.m_inicio.text.strip()

        if not nombre:
            self._show_snackbar("Debes ingresar el nombre del medicamento")
            return

        try:
            cantidad = float(cantidad_text) if cantidad_text else 0.0
        except Exception:
            cantidad = 0.0
        try:
            dosis = float(dosis_text) if dosis_text else 0.0
        except Exception:
            dosis = 0.0
        try:
            frecuencia = int(frecuencia_text) if frecuencia_text else 1
        except Exception:
            frecuencia = 1

        inicio_valido = None
        if inicio_text:
            try:
                datetime.strptime(inicio_text, "%Y-%m-%d %H:%M")
                inicio_valido = inicio_text
            except Exception:
                inicio_valido = None

        # Calcular fecha de finalización
        fecha_fin = self.calcular_fecha_fin(cantidad, dosis, frecuencia, inicio_valido)
        
        nuevo = {
            "nombre": nombre,
            "descripcion": descripcion or "Sin descripción",
            "presentacion": presentacion if presentacion != "Selecciona presentación" else "Sin especificar",
            "cantidad_total": cantidad,
            "cantidad_actual": cantidad,
            "dosis": dosis,
            "frecuencia_dias": frecuencia,
            "inicio": inicio_valido,
            "fecha_fin": fecha_fin,
            "ultima_alerta": None,
            "notificaciones_activas": False
        }

        # Control de duplicados (solo si NO estás editando)
        if not hasattr(self, "indice_editando"):
            for med in self.medicamentos:
                if med["nombre"].strip().lower() == nombre.strip().lower() and med["presentacion"].strip().lower() == presentacion.strip().lower():
                    self._show_snackbar("Ese medicamento ya está registrado")
                    return
            self.medicamentos.append(nuevo)
            self._show_snackbar(f"{nombre} agregado")
        else:
            idx = self.indice_editando
            if 0 <= idx < len(self.medicamentos):
                # Preservar cantidad actual al editar
                med_anterior = self.medicamentos[idx]
                nuevo["cantidad_actual"] = med_anterior.get("cantidad_actual", cantidad)
                # Recalcular fecha de fin con los nuevos datos
                nuevo["fecha_fin"] = self.calcular_fecha_fin(nuevo["cantidad_actual"], dosis, frecuencia, inicio_valido)
                # Debug: imprimir valores
                print(f"DEBUG EDIT: cantidad_actual={nuevo['cantidad_actual']}, dosis={dosis}, frecuencia={frecuencia}, inicio={inicio_valido}")
                print(f"DEBUG EDIT: nueva fecha_fin={nuevo['fecha_fin']}")
                self.medicamentos[idx] = nuevo
                del self.indice_editando
                self._show_snackbar(f"{nombre} actualizado")

        self.save_meds()
        self.refresh_list()
        # limpiar inputs
        self.limpiar_campos()

    def mostrar_opciones(self, index):
        med = self.medicamentos[index]
        
        # Calcular días restantes para mostrar en el popup
        dias_restantes = "N/A"
        if med.get("fecha_fin"):
            try:
                fecha_fin = datetime.strptime(med["fecha_fin"], "%Y-%m-%d %H:%M")
                dias_restantes = (fecha_fin - datetime.now()).days
                if dias_restantes < 0:
                    dias_restantes = "¡AGOTADO!"
                else:
                    dias_restantes = f"{dias_restantes} días"
            except:
                dias_restantes = "Error"
        
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(25))
        
        info_text = f"💊 {med['nombre']}\n📝 {med.get('descripcion', 'Sin descripción')}\n📦 {med['presentacion']}\n📊 Cantidad actual: {med.get('cantidad_actual', med['cantidad_total'])}\n💉 Dosis: {med['dosis']}\n⏰ Frecuencia: cada {med['frecuencia_dias']} días\n📅 Inicio: {med.get('inicio', 'No especificado')}\n⚠️ Se acaba en: {dias_restantes}"
        
        info_label = Label(
            text=info_text, 
            text_size=(dp(350), None), 
            halign='left',
            color=(0.2, 0.2, 0.2, 1),
            font_size='15sp'
        )
        content.add_widget(info_label)
        
        # Verificar si debe tomarse hoy y si ya se tomó
        debe_tomarse_hoy = self.es_dia_de_toma(med, datetime.now())
        ya_tomado = self.checklist_diario.get(str(index), False)
        
        # Verificar si necesita mostrar botón comprar (≤3 días restantes)
        mostrar_comprar = False
        if isinstance(dias_restantes, str) and "días" in dias_restantes:
            try:
                dias_num = int(dias_restantes.split()[0])
                if dias_num <= 3:
                    mostrar_comprar = True
            except:
                pass
        elif dias_restantes == "¡AGOTADO!":
            mostrar_comprar = True
        
        # Crear menú de opciones
        opciones_layout = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint_y=None, height=dp(40))
        
        btn_editar = Button(
            text="Editar",
            size_hint_x=0.33 if not mostrar_comprar else 0.25,
            background_color=(0.2, 0.6, 0.9, 1),
            color=(1, 1, 1, 1)
        )
        btn_editar.bind(on_release=lambda btn: self.editar_medicamento(index))
        
        btn_eliminar = Button(
            text="Eliminar",
            size_hint_x=0.33 if not mostrar_comprar else 0.25,
            background_color=(0.8, 0.3, 0.3, 1),
            color=(1, 1, 1, 1)
        )
        btn_eliminar.bind(on_release=lambda btn: self.eliminar_medicamento(index))
        
        btn_tomar = Button(
            text="Tomar",
            size_hint_x=0.33 if not mostrar_comprar else 0.25,
            background_color=(0.7, 0.5, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        btn_tomar.bind(on_release=lambda btn: [self.tomar_medicamento(index), popup.dismiss()])
        
        opciones_layout.add_widget(btn_editar)
        opciones_layout.add_widget(btn_eliminar)
        opciones_layout.add_widget(btn_tomar)
        
        # Solo agregar botón comprar si quedan ≤3 días
        if mostrar_comprar:
            btn_comprar = Button(
                text="Comprar",
                size_hint_x=0.25,
                background_color=(0.2, 0.7, 0.4, 1),
                color=(1, 1, 1, 1)
            )
            btn_comprar.bind(on_release=lambda btn: self.medicamento_comprado(index))
            opciones_layout.add_widget(btn_comprar)
        content.add_widget(opciones_layout)
        
        btn_cerrar = Button(
            text="✖️ Cerrar",
            size_hint_y=None,
            height=dp(40),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        content.add_widget(btn_cerrar)
        
        popup = Popup(
            title=med.get("nombre","Medicamento"),
            content=content,
            size_hint=(0.8, 0.6),
            background_color=(1, 1, 1, 1),
            separator_color=(0.2, 0.6, 0.9, 1)
        )
        
        btn_cerrar.bind(on_release=popup.dismiss)
        popup.open()

    def eliminar_medicamento(self, index):
        try:
            med = self.medicamentos.pop(index)
            self.save_meds()
            self.refresh_list()
            self._show_snackbar(f"{med.get('nombre','Medicamento')} eliminado")
        except Exception:
            pass

    def editar_medicamento(self, index):
        med = self.medicamentos[index]
        self.ids.m_nombre.text = med.get("nombre","")
        self.ids.m_descripcion.text = med.get("descripcion","")
        self.ids.m_presentacion.text = med.get("presentacion","Selecciona presentación")
        self.ids.m_cantidad.text = str(med.get("cantidad_total",""))
        self.ids.m_dosis.text = str(med.get("dosis",""))
        self.ids.m_frecuencia.text = str(med.get("frecuencia_dias",""))
        self.ids.m_inicio.text = med.get("inicio") or ""
        self.indice_editando = index
        self._show_snackbar(f"Editando: {med.get('nombre','')}")

    def _show_snackbar(self, texto):
        content = Label(
            text=texto,
            color=(0.2, 0.2, 0.2, 1),
            font_size='15sp'
        )
        popup = Popup(
            title="ℹ️ Información", 
            content=content, 
            size_hint=(0.7, 0.3), 
            auto_dismiss=True
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 1.2)

    def open_menu(self):
        dropdown = DropDown()
        
        for option in ['Gramos', 'Unidades', 'Mililitros', 'Tabletas']:
            btn = Button(
                text=option, 
                size_hint_y=None, 
                height=44,
                background_color=(0.9, 0.95, 1, 1),
                color=(0.1, 0.1, 0.1, 1),
                font_size='14sp'
            )
            btn.bind(on_release=lambda btn: self.set_item(btn.text))
            dropdown.add_widget(btn)
        
        dropdown.open(self.ids.m_presentacion)
        self.dropdown = dropdown

    def set_item(self, text_item):
        self.ids.m_presentacion.text = text_item
        self.dropdown.dismiss()

    def crear_grafica_barras(self):
        """Crea gráfica de barras de duración de medicamentos"""
        if not self.medicamentos:
            return None
        
        # Configurar estilo
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor('white')
        
        nombres = []
        dias = []
        colores = []
        
        for med in self.medicamentos:
            dias_restantes = self.calcular_dias_restantes(med)
            nombres.append(med['nombre'][:15] + '...' if len(med['nombre']) > 15 else med['nombre'])
            
            if isinstance(dias_restantes, str) and "días" in dias_restantes:
                try:
                    dias_num = int(dias_restantes.split()[0])
                    dias.append(dias_num)
                    
                    # Colores según urgencia
                    if dias_num <= 3:
                        colores.append('#FF6B6B')  # Rojo
                    elif dias_num <= 7:
                        colores.append('#FFB347')  # Naranja
                    else:
                        colores.append('#4ECDC4')  # Verde azulado
                except:
                    dias.append(0)
                    colores.append('#95A5A6')  # Gris
            else:
                dias.append(0)
                colores.append('#95A5A6')  # Gris
        
        # Crear gráfica
        bars = ax.bar(nombres, dias, color=colores, alpha=0.8, edgecolor='white', linewidth=2)
        
        # Personalizar
        ax.set_title('📊 Días Restantes por Medicamento', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Medicamentos', fontsize=12, fontweight='bold')
        ax.set_ylabel('Días Restantes', fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Rotar etiquetas del eje X
        plt.xticks(rotation=45, ha='right')
        
        # Agregar valores en las barras
        for bar, valor in zip(bars, dias):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{valor}d', ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen para Kivy
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def crear_grafica_pastel(self):
        """Crea gráfica de pastel del estado de medicamentos"""
        if not self.medicamentos:
            return None
        
        # Contar estados
        activos = 0
        por_agotar = 0
        agotados = 0
        
        for med in self.medicamentos:
            dias_restantes = self.calcular_dias_restantes(med)
            if isinstance(dias_restantes, str) and "días" in dias_restantes:
                try:
                    dias_num = int(dias_restantes.split()[0])
                    if dias_num <= 7:
                        por_agotar += 1
                    else:
                        activos += 1
                except:
                    agotados += 1
            else:
                agotados += 1
        
        # Crear gráfica
        fig, ax = plt.subplots(figsize=(8, 8))
        fig.patch.set_facecolor('white')
        
        labels = ['Activos', 'Por Agotar (≤7d)', 'Agotados']
        sizes = [activos, por_agotar, agotados]
        colors = ['#4ECDC4', '#FFB347', '#FF6B6B']
        explode = (0.05, 0.05, 0.05)
        
        # Filtrar valores cero
        filtered_data = [(label, size, color, exp) for label, size, color, exp in zip(labels, sizes, colors, explode) if size > 0]
        if filtered_data:
            labels, sizes, colors, explode = zip(*filtered_data)
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                         explode=explode, shadow=True, startangle=90)
        
        # Personalizar texto
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(12)
        
        for text in texts:
            text.set_fontsize(11)
            text.set_fontweight('bold')
        
        ax.set_title('📈 Estado de Medicamentos', fontsize=16, fontweight='bold', pad=20)
        
        # Convertir a imagen
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def crear_grafica_lineas(self):
        """Crea gráfica de líneas de tendencia de consumo"""
        if not self.medicamentos:
            return None
        
        # Simular datos de consumo por mes (últimos 6 meses)
        meses = ['Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene']
        consumo_total = []
        consumo_activos = []
        
        # Generar datos basados en medicamentos actuales
        base_consumo = len(self.medicamentos)
        for i in range(6):
            # Simular variación en el consumo
            variacion = np.random.randint(-2, 4)
            consumo_total.append(max(1, base_consumo + variacion))
            consumo_activos.append(max(0, consumo_total[i] - np.random.randint(0, 3)))
        
        # Crear gráfica
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor('white')
        
        ax.plot(meses, consumo_total, marker='o', linewidth=3, markersize=8, 
               color='#3498DB', label='Total Medicamentos', markerfacecolor='white', markeredgewidth=2)
        ax.plot(meses, consumo_activos, marker='s', linewidth=3, markersize=8, 
               color='#2ECC71', label='Medicamentos Activos', markerfacecolor='white', markeredgewidth=2)
        
        # Personalizar
        ax.set_title('📈 Tendencia de Consumo (Últimos 6 Meses)', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Mes', fontsize=12, fontweight='bold')
        ax.set_ylabel('Número de Medicamentos', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)
        
        # Agregar valores en los puntos
        for i, (total, activo) in enumerate(zip(consumo_total, consumo_activos)):
            ax.annotate(f'{total}', (i, total), textcoords="offset points", xytext=(0,10), ha='center', fontweight='bold')
            ax.annotate(f'{activo}', (i, activo), textcoords="offset points", xytext=(0,-15), ha='center', fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def mostrar_estadisticas(self):
        """Muestra estadísticas con gráficas visuales"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        
        # Fondo blanco sólido
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(1, 1, 1, 1)  # Blanco puro
            Rectangle(pos=content.pos, size=content.size)
        
        # Título
        titulo = Label(
            text="📊 Estadísticas y Gráficas",
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.2, 0.2, 0.2, 1)
        )
        content.add_widget(titulo)
        
        # Scroll para estadísticas
        scroll = ScrollView()
        stats_layout = BoxLayout(orientation='vertical', spacing=dp(15), size_hint_y=None)
        stats_layout.bind(minimum_height=stats_layout.setter('height'))
        
        if not self.medicamentos:
            no_data = Label(
                text="📭 No hay medicamentos para mostrar estadísticas",
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(40)
            )
            stats_layout.add_widget(no_data)
        else:
            # Estadísticas generales
            total_meds = len(self.medicamentos)
            meds_activos = len([m for m in self.medicamentos if self.calcular_dias_restantes(m) != "¡AGOTADO!"])
            
            stats_generales = Label(
                text=f"📈 RESUMEN GENERAL\n\n• Total medicamentos: {total_meds}\n• Medicamentos activos: {meds_activos}\n• Medicamentos agotados: {total_meds - meds_activos}",
                size_hint_y=None,
                height=dp(100),
                color=(0.2, 0.2, 0.2, 1),
                text_size=(dp(350), None),
                halign='left'
            )
            stats_layout.add_widget(stats_generales)
            
            # Gráfica de barras
            try:
                grafica_barras = self.crear_grafica_barras()
                if grafica_barras:
                    img_barras = Image(source='', size_hint_y=None, height=dp(250))
                    img_barras.texture = CoreImage(grafica_barras, ext='png').texture
                    stats_layout.add_widget(img_barras)
            except Exception as e:
                print(f"Error creando gráfica de barras: {e}")
            
            # Gráfica de pastel
            try:
                grafica_pastel = self.crear_grafica_pastel()
                if grafica_pastel:
                    img_pastel = Image(source='', size_hint_y=None, height=dp(300))
                    img_pastel.texture = CoreImage(grafica_pastel, ext='png').texture
                    stats_layout.add_widget(img_pastel)
            except Exception as e:
                print(f"Error creando gráfica de pastel: {e}")
            
            # Gráfica de líneas
            try:
                grafica_lineas = self.crear_grafica_lineas()
                if grafica_lineas:
                    img_lineas = Image(source='', size_hint_y=None, height=dp(250))
                    img_lineas.texture = CoreImage(grafica_lineas, ext='png').texture
                    stats_layout.add_widget(img_lineas)
            except Exception as e:
                print(f"Error creando gráfica de líneas: {e}")
            
            # Estadísticas de consumo
            duraciones = []
            for med in self.medicamentos:
                if med.get('fecha_inicio') and med.get('fecha_fin'):
                    try:
                        inicio = datetime.strptime(med['fecha_inicio'], "%Y-%m-%d %H:%M")
                        fin = datetime.strptime(med['fecha_fin'], "%Y-%m-%d %H:%M")
                        duracion = (fin - inicio).days
                        if duracion > 0:
                            duraciones.append(duracion)
                    except:
                        continue
            
            if duraciones:
                promedio_duracion = sum(duraciones) / len(duraciones)
                duracion_max = max(duraciones)
                duracion_min = min(duraciones)
                
                consumo_stats = Label(
                    text=f"📈 ANÁLISIS DE CONSUMO\n\n• Duración promedio: {promedio_duracion:.1f} días\n• Duración máxima: {duracion_max} días\n• Duración mínima: {duracion_min} días\n• Medicamentos analizados: {len(duraciones)}",
                    size_hint_y=None,
                    height=dp(120),
                    color=(0.2, 0.2, 0.2, 1),
                    text_size=(dp(350), None),
                    halign='left'
                )
                stats_layout.add_widget(consumo_stats)
        
        scroll.add_widget(stats_layout)
        content.add_widget(scroll)
        
        # Botón cerrar
        btn_cerrar = Button(
            text="✖️ Cerrar",
            size_hint_y=None,
            height=dp(40),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        
        popup = Popup(
            title="Estadísticas",
            content=content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 1),  # Fondo blanco del popup
            separator_color=(0.2, 0.6, 0.9, 1)  # Línea azul del título
        )
        
        btn_cerrar.bind(on_release=popup.dismiss)
        content.add_widget(btn_cerrar)
        
        popup.open()
    
    def mostrar_calendario(self):
        """Muestra calendario con próximas tomas y fechas importantes"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        
        # Fondo blanco sólido
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(1, 1, 1, 1)  # Blanco puro
            Rectangle(pos=content.pos, size=content.size)
        
        # Título
        titulo = Label(
            text="📅 Calendario de Medicamentos",
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.2, 0.2, 0.2, 1)
        )
        content.add_widget(titulo)
        
        # Scroll para calendario
        scroll = ScrollView()
        cal_layout = BoxLayout(orientation='vertical', spacing=dp(15), size_hint_y=None)
        cal_layout.bind(minimum_height=cal_layout.setter('height'))
        
        if not self.medicamentos:
            no_data = Label(
                text="📭 No hay medicamentos programados",
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(40)
            )
            cal_layout.add_widget(no_data)
        else:
            # Fecha actual
            hoy = datetime.now()
            
            # Sección: Hoy
            hoy_titulo = Label(
                text=f"🗓️ HOY - {hoy.strftime('%d/%m/%Y')}",
                size_hint_y=None,
                height=dp(30),
                color=(0.2, 0.2, 0.2, 1),
                font_size='16sp'
            )
            cal_layout.add_widget(hoy_titulo)
            
            medicamentos_hoy = []
            for i, med in enumerate(self.medicamentos):
                if self.es_dia_de_toma(med, hoy):
                    medicamentos_hoy.append(i)
            
            if medicamentos_hoy:
                for i in medicamentos_hoy:
                    item_hoy = Button(
                        text=f"💊 {self.medicamentos[i]['nombre']} - Dosis: {self.medicamentos[i]['dosis']}",
                        size_hint_y=None,
                        height=dp(40),
                        background_color=(0.9, 1, 0.9, 1),
                        color=(0.2, 0.2, 0.2, 1)
                    )
                    cal_layout.add_widget(item_hoy)
            else:
                sin_tomas = Label(
                    text="✅ No hay medicamentos programados para hoy",
                    size_hint_y=None,
                    height=dp(30),
                    color=(0.5, 0.5, 0.5, 1)
                )
                cal_layout.add_widget(sin_tomas)
            
            # Próximos 7 días
            proximos_titulo = Label(
                text="📋 PRÓXIMOS 7 DÍAS",
                size_hint_y=None,
                height=dp(30),
                color=(0.2, 0.2, 0.2, 1),
                font_size='16sp'
            )
            cal_layout.add_widget(proximos_titulo)
            
            for i in range(1, 8):
                fecha = hoy + timedelta(days=i)
                dia_nombre = fecha.strftime('%A')
                fecha_str = fecha.strftime('%d/%m')
                
                medicamentos_dia = []
                for med in self.medicamentos:
                    if self.es_dia_de_toma(med, fecha):
                        medicamentos_dia.append(med)
                
                # Layout para cada día
                dia_layout = BoxLayout(orientation='vertical', spacing=dp(3), size_hint_y=None)
                dia_layout.bind(minimum_height=dia_layout.setter('height'))
                
                dia_header = Label(
                    text=f"📆 {dia_nombre.capitalize()} {fecha_str}",
                    size_hint_y=None,
                    height=dp(25),
                    color=(0.3, 0.3, 0.3, 1),
                    font_size='14sp'
                )
                dia_layout.add_widget(dia_header)
                
                if medicamentos_dia:
                    for med in medicamentos_dia:
                        med_item = Label(
                            text=f"  💊 {med['nombre']} ({med['dosis']})",
                            size_hint_y=None,
                            height=dp(25),
                            color=(0.4, 0.4, 0.4, 1),
                            text_size=(dp(300), None),
                            halign='left'
                        )
                        dia_layout.add_widget(med_item)
                else:
                    sin_med = Label(
                        text="  ✅ Sin medicamentos",
                        size_hint_y=None,
                        height=dp(25),
                        color=(0.6, 0.6, 0.6, 1),
                        text_size=(dp(300), None),
                        halign='left'
                    )
                    dia_layout.add_widget(sin_med)
                
                cal_layout.add_widget(dia_layout)
            
            # Fechas de finalización próximas
            finalizacion_titulo = Label(
                text="⚠️ PRÓXIMAS FINALIZACIONES",
                size_hint_y=None,
                height=dp(30),
                color=(0.2, 0.2, 0.2, 1),
                font_size='16sp'
            )
            cal_layout.add_widget(finalizacion_titulo)
            
            finalizaciones = []
            for med in self.medicamentos:
                dias_restantes = self.calcular_dias_restantes(med)
                if isinstance(dias_restantes, str) and "días" in dias_restantes:
                    try:
                        dias_num = int(dias_restantes.split()[0])
                        if dias_num <= 14:  # Próximas 2 semanas
                            finalizaciones.append((med, dias_num))
                    except:
                        continue
            
            finalizaciones.sort(key=lambda x: x[1])  # Ordenar por días restantes
            
            if finalizaciones:
                for med, dias in finalizaciones:
                    if dias <= 3:
                        color = (1, 0.9, 0.9, 1)  # Rojo claro
                        emoji = "🚨"
                    elif dias <= 7:
                        color = (1, 0.95, 0.8, 1)  # Amarillo claro
                        emoji = "⚠️"
                    else:
                        color = (0.95, 1, 0.95, 1)  # Verde claro
                        emoji = "📋"
                    
                    fin_item = Button(
                        text=f"{emoji} {med['nombre']} - {dias} días restantes",
                        size_hint_y=None,
                        height=dp(40),
                        background_color=color,
                        color=(0.2, 0.2, 0.2, 1)
                    )
                    cal_layout.add_widget(fin_item)
            else:
                sin_fin = Label(
                    text="✅ No hay finalizaciones próximas",
                    size_hint_y=None,
                    height=dp(30),
                    color=(0.5, 0.5, 0.5, 1)
                )
                cal_layout.add_widget(sin_fin)
        
        scroll.add_widget(cal_layout)
        content.add_widget(scroll)
        
        # Botón cerrar
        btn_cerrar = Button(
            text="✖️ Cerrar",
            size_hint_y=None,
            height=dp(40),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        
        popup = Popup(
            title="Calendario",
            content=content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 1),  # Fondo blanco del popup
            separator_color=(0.2, 0.7, 0.5, 1)  # Línea verde del título
        )
        
        btn_cerrar.bind(on_release=popup.dismiss)
        content.add_widget(btn_cerrar)
        
        popup.open()
    
    def es_dia_de_toma(self, medicamento, fecha):
        """Determina si un medicamento debe tomarse en una fecha específica"""
        # Verificar fecha de inicio - usar tanto 'fecha_inicio' como 'inicio'
        fecha_inicio_str = medicamento.get('fecha_inicio') or medicamento.get('inicio')
        if not fecha_inicio_str:
            # Si no hay fecha de inicio, asumir que debe tomarse (medicamento activo)
            return True
        
        try:
            inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d %H:%M")
            frecuencia = int(medicamento.get('frecuencia_dias', 1))
            
            # Calcular días desde el inicio
            dias_desde_inicio = (fecha.date() - inicio.date()).days
            
            # Verificar si es día de toma
            return dias_desde_inicio >= 0 and dias_desde_inicio % frecuencia == 0
        except:
            # Si hay error en el parsing, asumir que debe tomarse
            return True
    
    def calcular_dias_restantes(self, medicamento):
        """Calcula días restantes para un medicamento"""
        if not medicamento.get("fecha_fin"):
            return "Sin fecha"
        
        try:
            fecha_fin = datetime.strptime(medicamento["fecha_fin"], "%Y-%m-%d %H:%M")
            dias_restantes = (fecha_fin - datetime.now()).days
            if dias_restantes < 0:
                return "¡AGOTADO!"
            else:
                return f"{dias_restantes} días"
        except:
            return "Error"
    
    def mostrar_historial(self):
        """Muestra el historial de notificaciones"""
        historial = self.historial_notificaciones
        
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        
        # Fondo blanco sólido
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(1, 1, 1, 1)  # Blanco puro
            Rectangle(pos=content.pos, size=content.size)
        
        # Título
        titulo = Label(
            text="📋 Historial de Notificaciones",
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.2, 0.2, 0.2, 1)
        )
        content.add_widget(titulo)
        
        # Lista scrolleable
        scroll = ScrollView()
        lista_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        lista_layout.bind(minimum_height=lista_layout.setter('height'))
        
        if not historial:
            no_data = Label(
                text="📭 No hay notificaciones en el historial",
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(40)
            )
            lista_layout.add_widget(no_data)
        else:
            for notif in reversed(historial[-20:]):  # Últimas 20
                # Color según tipo
                if notif['tipo'] == 'dosis':
                    bg_color = (0.9, 1, 0.9, 1)  # Verde claro
                    emoji = "💊"
                elif notif['tipo'] == 'stock_bajo':
                    bg_color = (1, 0.95, 0.8, 1)  # Amarillo claro
                    emoji = "⚠️"
                else:
                    bg_color = (1, 0.9, 0.9, 1)  # Rojo claro
                    emoji = "🚨"
                
                item = Button(
                    text=f"{emoji} {notif['medicamento']}\n{notif['mensaje']}\n🕐 {notif['fecha']}",
                    size_hint_y=None,
                    height=dp(70),
                    background_color=bg_color,
                    color=(0.2, 0.2, 0.2, 1),
                    text_size=(dp(300), None),
                    halign='left',
                    valign='middle'
                )
                lista_layout.add_widget(item)
        
        scroll.add_widget(lista_layout)
        content.add_widget(scroll)
        
        # Botones
        buttons_layout = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(50))
        
        btn_limpiar = Button(
            text="🗑️ Limpiar",
            background_color=(0.8, 0.3, 0.3, 1),
            color=(1, 1, 1, 1)
        )
        btn_limpiar.bind(on_release=lambda x: self.limpiar_historial())
        
        btn_cerrar = Button(
            text="✖️ Cerrar",
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        
        popup = Popup(
            title="Historial de Notificaciones",
            content=content,
            size_hint=(0.9, 0.8),
            background_color=(1, 1, 1, 1),  # Fondo blanco del popup
            separator_color=(0.2, 0.4, 0.7, 1)  # Línea azul del título
        )
        
        btn_cerrar.bind(on_release=popup.dismiss)
        
        buttons_layout.add_widget(btn_limpiar)
        buttons_layout.add_widget(btn_cerrar)
        content.add_widget(buttons_layout)
        
        popup.open()

    def limpiar_historial(self):
        """Limpia el historial de notificaciones"""
        self.historial_notificaciones = []
        self.save_historial()
        self._show_snackbar("Historial limpiado")

    def limpiar_campos(self):
        self.ids.m_nombre.text = ""
        self.ids.m_descripcion.text = ""
        self.ids.m_presentacion.text = "Selecciona presentación"
        self.ids.m_cantidad.text = ""
        self.ids.m_dosis.text = ""
        self.ids.m_frecuencia.text = ""
        self.ids.m_inicio.text = ""

    # ---------------- Sistema de notificaciones ----------------
    def calcular_fecha_fin(self, cantidad, dosis, frecuencia, inicio=None):
        """Calcula cuándo se acabará el medicamento"""
        if cantidad <= 0 or dosis <= 0 or frecuencia <= 0:
            return None
        
        # Días que durará el medicamento
        dias_duracion = (cantidad / dosis) * frecuencia
        
        # Fecha de inicio (ahora si no se especifica)
        if inicio:
            try:
                fecha_inicio = datetime.strptime(inicio, "%Y-%m-%d %H:%M")
            except:
                fecha_inicio = datetime.now()
        else:
            fecha_inicio = datetime.now()
        
        # Calcular fecha de finalización
        fecha_fin = fecha_inicio + timedelta(days=dias_duracion)
        return fecha_fin.strftime("%Y-%m-%d %H:%M")

    def start_notification_system(self):
        """Inicia el sistema de notificaciones en segundo plano"""
        if self.notification_thread is None or not self.notification_thread.is_alive():
            self.stop_notifications = False
            self.notification_thread = threading.Thread(target=self.notification_worker, daemon=True)
            self.notification_thread.start()

    def start_dose_reminders(self):
        """Inicia el sistema de recordatorios de dosis"""
        if self.dose_reminder_thread is None or not self.dose_reminder_thread.is_alive():
            self.dose_reminder_thread = threading.Thread(target=self.dose_reminder_worker, daemon=True)
            self.dose_reminder_thread.start()

    def dose_reminder_worker(self):
        """Hilo que verifica recordatorios de dosis cada 30 minutos"""
        while not self.stop_notifications:
            try:
                Clock.schedule_once(lambda dt: self.check_dose_reminders(), 0)
                # Esperar 30 minutos (1800 segundos)
                for _ in range(180):  # 30 minutos dividido en intervalos de 10 segundos
                    if self.stop_notifications:
                        break
                    time.sleep(10)
            except Exception:
                break

    def notification_worker(self):
        """Hilo que verifica medicamentos cada 4 horas"""
        while not self.stop_notifications:
            try:
                Clock.schedule_once(lambda dt: self.check_medications(), 0)
                # Esperar 4 horas (14400 segundos)
                for _ in range(1440):  # 4 horas dividido en intervalos de 10 segundos
                    if self.stop_notifications:
                        break
                    time.sleep(10)
            except Exception:
                break

    def check_dose_reminders(self):
        """Verifica si es hora de tomar algún medicamento"""
        ahora = datetime.now()
        
        for i, med in enumerate(self.medicamentos):
            if not med.get("inicio"):
                continue
                
            try:
                fecha_inicio = datetime.strptime(med["inicio"], "%Y-%m-%d %H:%M")
                frecuencia_horas = med["frecuencia_dias"] * 24
                
                # Calcular cuántas horas han pasado desde el inicio
                horas_transcurridas = (ahora - fecha_inicio).total_seconds() / 3600
                
                # Verificar si es momento de tomar la dosis
                if horas_transcurridas > 0 and horas_transcurridas % frecuencia_horas < 0.5:  # Ventana de 30 minutos
                    # Verificar si ya se notificó en la última hora
                    ultima_notif = med.get("ultima_notif_dosis")
                    if not ultima_notif or (ahora - datetime.strptime(ultima_notif, "%Y-%m-%d %H:%M:%S")).total_seconds() > 3600:
                        med["ultima_notif_dosis"] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                        self.save_meds()
                        self.mostrar_recordatorio_dosis(i, med)
                        
            except Exception:
                continue

    def check_medications(self):
        """Verifica si algún medicamento necesita notificación"""
        ahora = datetime.now()
        
        for i, med in enumerate(self.medicamentos):
            if not med.get("fecha_fin"):
                continue
                
            try:
                fecha_fin = datetime.strptime(med["fecha_fin"], "%Y-%m-%d %H:%M")
                dias_restantes = (fecha_fin - ahora).days
                
                # Si faltan 3 días o menos y no se han activado las notificaciones
                if dias_restantes <= 3 and not med.get("notificaciones_activas", False):
                    med["notificaciones_activas"] = True
                    self.save_meds()
                    mensaje = f"Tu medicamento '{med['nombre']}' se acabará en {dias_restantes} días"
                    self.agregar_al_historial("stock_bajo", med['nombre'], mensaje)
                    self.mostrar_notificacion_compra(i, med, dias_restantes)
                    
            except Exception:
                continue

    def play_notification_sound(self):
        """Reproduce sonido de notificación"""
        try:
            if winsound:
                # Sonido del sistema de Windows
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            else:
                # Para Android, usar vibración si está disponible
                try:
                    from plyer import vibrator
                    vibrator.vibrate(0.5)  # Vibrar por 0.5 segundos
                except ImportError:
                    pass
        except:
            pass  # Si no puede reproducir sonido/vibración, continúa sin error

    def marcar_completado(self, indice):
        """Marca un medicamento como completado en el checklist diario"""
        if 0 <= indice < len(self.medicamentos):
            medicamento = self.medicamentos[indice]
            
            # Verificar si debe tomarse hoy
            if not self.es_dia_de_toma(medicamento, datetime.now()):
                self.mostrar_notificacion(
                    "ℹ️ Información",
                    f"{medicamento['nombre']} no debe tomarse hoy según su frecuencia.",
                    "info"
                )
                return
            
            # Alternar estado de completado
            ya_completado = self.checklist_diario.get(str(indice), False)
            
            if not ya_completado:
                # Marcar como completado
                self.checklist_diario[str(indice)] = True
                self.save_checklist()
                
                # Reducir cantidad actual
                cantidad_actual = medicamento.get('cantidad_actual', medicamento['cantidad_total'])
                if cantidad_actual > 0:
                    medicamento['cantidad_actual'] = cantidad_actual - 1
                    
                    # Recalcular fecha de fin
                    if medicamento.get('fecha_inicio'):
                        try:
                            fecha_inicio = datetime.strptime(medicamento['fecha_inicio'], "%Y-%m-%d %H:%M")
                            dias_restantes = medicamento['cantidad_actual'] * medicamento['frecuencia_dias']
                            nueva_fecha_fin = fecha_inicio + timedelta(days=dias_restantes)
                            medicamento['fecha_fin'] = nueva_fecha_fin.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    self.save_meds()
                
                # Notificación de felicitación personalizada
                nombre_usuario = self.usuario_actual if self.usuario_actual else "Usuario"
                mensajes_felicitacion = [
                    f"🎉 ¡Excelente, {nombre_usuario}! Has tomado {medicamento['nombre']} correctamente.",
                    f"✨ ¡Bien hecho, {nombre_usuario}! {medicamento['nombre']} completado por hoy.",
                    f"🌟 ¡Perfecto, {nombre_usuario}! Sigues tu tratamiento de {medicamento['nombre']} al día.",
                    f"👏 ¡Genial, {nombre_usuario}! {medicamento['nombre']} tomado correctamente.",
                    f"🎊 ¡Fantástico, {nombre_usuario}! Mantienes tu rutina de {medicamento['nombre']}."
                ]
                
                import random
                mensaje = random.choice(mensajes_felicitacion)
                
                self._show_snackbar(mensaje)
                
                # Sonido de celebración
                if winsound:
                    try:
                        # Sonido de éxito más alegre
                        winsound.Beep(800, 200)  # Nota alta
                        winsound.Beep(1000, 200)  # Nota más alta
                        winsound.Beep(1200, 300)  # Nota de celebración
                    except:
                        pass
                
                # Verificar si se completaron todos los medicamentos del día
                self.verificar_dia_completado()
                
            else:
                # Desmarcar como completado
                self.checklist_diario[str(indice)] = False
                self.save_checklist()
                
                self.mostrar_notificacion(
                    "↩️ Desmarcado",
                    f"{medicamento['nombre']} desmarcado del checklist.",
                    "info"
                )
            
            self.refresh_list()
    
    def verificar_dia_completado(self):
        """Verifica si se completaron todos los medicamentos del día"""
        medicamentos_hoy = []
        for i, med in enumerate(self.medicamentos):
            if self.es_dia_de_toma(med, datetime.now()):
                medicamentos_hoy.append(i)
        
        if not medicamentos_hoy:
            return
        
        # Verificar si todos están completados
        todos_completados = all(
            self.checklist_diario.get(str(i), False) for i in medicamentos_hoy
        )
        
        if todos_completados:
            nombre_usuario = self.usuario_actual if self.usuario_actual else "Usuario"
            mensaje_completado = f"🎉 ¡Felicitaciones, {nombre_usuario}! Has completado todos tus medicamentos de hoy. ¡Excelente trabajo cuidando tu salud!"
            self._show_snackbar(mensaje_completado)
            
            # Sonido especial de celebración completa
            if winsound:
                try:
                    for freq in [600, 700, 800, 900, 1000, 1100, 1200]:
                        winsound.Beep(freq, 100)
                except:
                    pass

    def mostrar_recordatorio_dosis(self, index, med):
        """Muestra recordatorio para tomar dosis"""
        self.play_notification_sound()
        
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        
        # Fondo con alto contraste - azul oscuro con contenido claro
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(0.1, 0.2, 0.4, 1)  # Azul oscuro
            Rectangle(pos=content.pos, size=content.size)
            Color(0.9, 0.95, 1, 1)  # Azul muy claro para contenido
            Rectangle(pos=(content.x + dp(10), content.y + dp(10)), size=(content.width - dp(20), content.height - dp(20)))
        
        mensaje = f"💊 ¡HORA DE TU MEDICAMENTO!\n\n'{med['nombre']}'\n{med.get('descripcion', '')}\n\nDosis: {med['dosis']}\nEs hora de tomar tu medicamento."
        
        info_label = Label(
            text=mensaje,
            text_size=(dp(320), None),
            halign='center',
            color=(0.2, 0.2, 0.2, 1),
            font_size='16sp'
        )
        content.add_widget(info_label)
        
        buttons_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        
        btn_tomado = Button(
            text="✅ Ya lo tomé", 
            size_hint_x=0.5,
            background_color=(0.2, 0.7, 0.4, 1),
            color=(1, 1, 1, 1),
            font_size='14sp'
        )
        btn_recordar = Button(
            text="⏰ Recordar en 15 min", 
            size_hint_x=0.5,
            background_color=(0.7, 0.5, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='14sp'
        )
        
        popup = Popup(title="💊 Recordatorio de Medicamento", content=content, size_hint=(0.9, 0.6))
        
        btn_tomado.bind(on_release=lambda x: (popup.dismiss(), self.marcar_dosis_tomada(index)))
        btn_recordar.bind(on_release=lambda x: (popup.dismiss(), self.posponer_recordatorio(index, 15)))
        
        buttons_layout.add_widget(btn_tomado)
        buttons_layout.add_widget(btn_recordar)
        content.add_widget(buttons_layout)
        
        # Agregar al historial
        mensaje_historial = f"Recordatorio de dosis para {med['nombre']}"
        self.agregar_al_historial("dosis", med['nombre'], mensaje_historial)
        
        popup.open()

    def marcar_dosis_tomada(self, index):
        """Marca que se tomó la dosis"""
        med = self.medicamentos[index]
        # Reducir cantidad actual
        cantidad_actual = med.get("cantidad_actual", med["cantidad_total"])
        nueva_cantidad = max(0, cantidad_actual - med["dosis"])
        med["cantidad_actual"] = nueva_cantidad
        
        # Recalcular fecha de fin si es necesario
        if nueva_cantidad <= 0:
            mensaje = f"¡MEDICAMENTO AGOTADO! {med['nombre']} se ha terminado"
            self.agregar_al_historial("agotado", med['nombre'], mensaje)
        else:
            # Recalcular fecha de fin con la nueva cantidad
            if med.get("inicio"):
                med["fecha_fin"] = self.calcular_fecha_fin(nueva_cantidad, med["dosis"], med["frecuencia_dias"], med["inicio"])
        
        self.save_meds()
        self.refresh_list()
        self._show_snackbar(f"Dosis de {med['nombre']} registrada")
    
    def tomar_medicamento(self, indice):
        """Registra la toma de un medicamento (método legacy)"""
        if 0 <= indice < len(self.medicamentos):
            medicamento = self.medicamentos[indice]
            
            # Reducir cantidad actual
            cantidad_actual = medicamento.get('cantidad_actual', medicamento['cantidad_total'])
            if cantidad_actual > 0:
                medicamento['cantidad_actual'] = cantidad_actual - 1
                
                # Recalcular fecha de fin si es necesario
                if medicamento.get('fecha_inicio'):
                    try:
                        fecha_inicio = datetime.strptime(medicamento['fecha_inicio'], "%Y-%m-%d %H:%M")
                        dias_restantes = medicamento['cantidad_actual'] * medicamento['frecuencia_dias']
                        nueva_fecha_fin = fecha_inicio + timedelta(days=dias_restantes)
                        medicamento['fecha_fin'] = nueva_fecha_fin.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                # SINCRONIZAR CON CHECKLIST - marcar como completado automáticamente
                self.checklist_diario[str(indice)] = True
                self.save_checklist()
                
                # Sonido de celebración
                if winsound:
                    try:
                        winsound.Beep(800, 200)
                        winsound.Beep(1000, 200)
                        winsound.Beep(1200, 300)
                    except:
                        pass
                
                # Verificar si el día está completado
                self.verificar_dia_completado()
                
                self.save_meds()
                self.refresh_list()
                
                # Notificación de confirmación
                self._show_snackbar(f"💊 Has tomado {medicamento['nombre']}. Quedan {medicamento['cantidad_actual']} dosis.")
                
                # Verificar si se está agotando
                if medicamento['cantidad_actual'] <= 3:
                    self._show_snackbar(f"⚠️ {medicamento['nombre']} se está agotando. Quedan solo {medicamento['cantidad_actual']} dosis.")
            else:
                self._show_snackbar(f"❌ No quedan dosis de {medicamento['nombre']}. Necesitas comprar más.")

    def posponer_recordatorio(self, index, minutos):
        """Pospone el recordatorio por X minutos"""
        med = self.medicamentos[index]
        # Programar recordatorio para más tarde
        Clock.schedule_once(lambda dt: self.mostrar_recordatorio_dosis(index, med), minutos * 60)
        self._show_snackbar(f"Recordatorio pospuesto {minutos} minutos")

    def mostrar_checklist(self):
        """Muestra vista dedicada de checklist con chulos visuales"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        
        # Fondo blanco sólido
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(1, 1, 1, 1)  # Blanco puro
            Rectangle(pos=content.pos, size=content.size)
        
        # Título con progreso
        hoy = datetime.now()
        medicamentos_hoy = []
        completados_hoy = 0
        
        for i, med in enumerate(self.medicamentos):
            if self.es_dia_de_toma(med, hoy):
                medicamentos_hoy.append(i)
                if self.checklist_diario.get(str(i), False):
                    completados_hoy += 1
        
        total_hoy = len(medicamentos_hoy)
        progreso_texto = f"✅ Checklist Diario - {completados_hoy}/{total_hoy} completados"
        
        titulo = Label(
            text=progreso_texto,
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.2, 0.2, 0.2, 1)
        )
        content.add_widget(titulo)
        
        # Scroll para checklist
        scroll = ScrollView()
        checklist_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        checklist_layout.bind(minimum_height=checklist_layout.setter('height'))
        
        if not medicamentos_hoy:
            no_meds = Label(
                text="🎉 ¡No hay medicamentos programados para hoy!\n\nDisfruta tu día libre de medicamentos.",
                color=(0.2, 0.7, 0.4, 1),
                size_hint_y=None,
                height=dp(80),
                text_size=(dp(350), None),
                halign='center',
                font_size='16sp'
            )
            checklist_layout.add_widget(no_meds)
        else:
            # Crear items de checklist
            for i in medicamentos_hoy:
                med = self.medicamentos[i]
                ya_completado = self.checklist_diario.get(str(i), False)
                
                # Layout para cada item
                item_layout = BoxLayout(
                    orientation='horizontal', 
                    spacing=dp(15), 
                    size_hint_y=None, 
                    height=dp(80),
                    padding=(dp(15), dp(10))
                )
                
                # Fondo del item
                with item_layout.canvas.before:
                    if ya_completado:
                        Color(0.9, 1, 0.9, 1)  # Verde claro para completado
                    else:
                        Color(0.98, 0.98, 1, 1)  # Azul muy claro para pendiente
                    Rectangle(pos=item_layout.pos, size=item_layout.size)
                
                # Checkbox grande
                checkbox = Button(
                    text="✅" if ya_completado else "☐",
                    size_hint_x=None,
                    width=dp(60),
                    font_size='24sp',
                    background_color=(0.2, 0.8, 0.2, 1) if ya_completado else (0.9, 0.9, 0.9, 1),
                    color=(1, 1, 1, 1) if ya_completado else (0.5, 0.5, 0.5, 1)
                )
                # Usar lambda con valor por defecto para capturar el índice correctamente
                checkbox.bind(on_release=lambda btn, medicamento_idx=i: self.toggle_checklist_item(medicamento_idx))
                
                # Información del medicamento
                info_text = f"💊 {med['nombre']}\n📋 {med.get('descripcion', 'Sin descripción')}\n💉 Dosis: {med['dosis']}"
                
                info_label = Label(
                    text=info_text,
                    text_size=(dp(250), None),
                    halign='left',
                    valign='middle',
                    color=(0.2, 0.2, 0.2, 1),
                    font_size='14sp'
                )
                
                # Estado visual
                estado_label = Label(
                    text="✅\nCOMPLETADO" if ya_completado else "⏰\nPENDIENTE",
                    size_hint_x=None,
                    width=dp(80),
                    color=(0.2, 0.7, 0.2, 1) if ya_completado else (0.7, 0.5, 0.2, 1),
                    font_size='12sp',
                    halign='center'
                )
                
                item_layout.add_widget(checkbox)
                item_layout.add_widget(info_label)
                item_layout.add_widget(estado_label)
                checklist_layout.add_widget(item_layout)
        
        scroll.add_widget(checklist_layout)
        content.add_widget(scroll)
        
        # Barra de progreso visual
        if total_hoy > 0:
            progreso_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None, height=dp(50))
            
            progreso_label = Label(
                text=f"Progreso del día: {completados_hoy}/{total_hoy} ({int(completados_hoy/total_hoy*100)}%)",
                size_hint_y=None,
                height=dp(25),
                color=(0.2, 0.2, 0.2, 1),
                font_size='14sp'
            )
            
            # Barra de progreso visual
            barra_bg = Widget(size_hint_y=None, height=dp(20))
            with barra_bg.canvas:
                Color(0.9, 0.9, 0.9, 1)  # Fondo gris
                Rectangle(pos=barra_bg.pos, size=barra_bg.size)
                Color(0.2, 0.8, 0.2, 1)  # Verde para progreso
                Rectangle(pos=barra_bg.pos, size=(barra_bg.width * (completados_hoy/total_hoy), barra_bg.height))
            
            progreso_layout.add_widget(progreso_label)
            progreso_layout.add_widget(barra_bg)
            content.add_widget(progreso_layout)
        
        # Botones de acción
        buttons_layout = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(50))
        
        btn_completar_todos = Button(
            text="✅ Completar Todos",
            size_hint_x=0.5,
            background_color=(0.2, 0.8, 0.2, 1),
            color=(1, 1, 1, 1),
            disabled=completados_hoy == total_hoy
        )
        btn_completar_todos.bind(on_release=lambda x: [self.completar_todos_medicamentos(), popup.dismiss()])
        
        btn_cerrar = Button(
            text="✖️ Cerrar",
            size_hint_x=0.5,
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1)
        )
        
        buttons_layout.add_widget(btn_completar_todos)
        buttons_layout.add_widget(btn_cerrar)
        content.add_widget(buttons_layout)
        
        popup = Popup(
            title="✅ Checklist Diario",
            content=content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 1),
            separator_color=(0.2, 0.8, 0.4, 1)
        )
        
        btn_cerrar.bind(on_release=popup.dismiss)
        popup.open()
    
    def toggle_checklist_item(self, indice):
        """Alterna el estado de completado de un item del checklist"""
        if 0 <= indice < len(self.medicamentos):
            medicamento = self.medicamentos[indice]
            
            # Verificar si debe tomarse hoy
            if not self.es_dia_de_toma(medicamento, datetime.now()):
                self._show_snackbar(f"{medicamento['nombre']} no debe tomarse hoy.")
                return
            
            # Alternar estado
            ya_completado = self.checklist_diario.get(str(indice), False)
            
            if not ya_completado:
                # Marcar como completado
                self.checklist_diario[str(indice)] = True
                self.save_checklist()
                
                # Reducir cantidad
                cantidad_actual = medicamento.get('cantidad_actual', medicamento['cantidad_total'])
                if cantidad_actual > 0:
                    medicamento['cantidad_actual'] = cantidad_actual - 1
                    
                    # Recalcular fecha de fin
                    if medicamento.get('fecha_inicio'):
                        try:
                            fecha_inicio = datetime.strptime(medicamento['fecha_inicio'], "%Y-%m-%d %H:%M")
                            dias_restantes = medicamento['cantidad_actual'] * medicamento['frecuencia_dias']
                            nueva_fecha_fin = fecha_inicio + timedelta(days=dias_restantes)
                            medicamento['fecha_fin'] = nueva_fecha_fin.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    self.save_meds()
                
                # Sonido y notificación de celebración
                if winsound:
                    try:
                        winsound.Beep(800, 200)
                        winsound.Beep(1000, 200)
                        winsound.Beep(1200, 300)
                    except:
                        pass
                
                self._show_snackbar(f"🎉 ¡{medicamento['nombre']} completado!")
                
                # Verificar día completado
                self.verificar_dia_completado()
                
            else:
                # Desmarcar
                self.checklist_diario[str(indice)] = False
                self.save_checklist()
                self._show_snackbar(f"↩️ {medicamento['nombre']} desmarcado")
            
            self.refresh_list()
            # No reabrir checklist automáticamente para evitar crashes
    
    def completar_todos_medicamentos(self):
        """Marca todos los medicamentos del día como completados"""
        hoy = datetime.now()
        medicamentos_hoy = []
        
        for i, med in enumerate(self.medicamentos):
            if self.es_dia_de_toma(med, hoy):
                medicamentos_hoy.append(i)
        
        completados = 0
        for i in medicamentos_hoy:
            if not self.checklist_diario.get(str(i), False):
                self.checklist_diario[str(i)] = True
                
                # Reducir cantidad
                medicamento = self.medicamentos[i]
                cantidad_actual = medicamento.get('cantidad_actual', medicamento['cantidad_total'])
                if cantidad_actual > 0:
                    medicamento['cantidad_actual'] = cantidad_actual - 1
                
                completados += 1
        
        if completados > 0:
            self.save_checklist()
            self.save_meds()
            
            # Sonido especial para completar todos
            if winsound:
                try:
                    for freq in [600, 700, 800, 900, 1000, 1100, 1200]:
                        winsound.Beep(freq, 100)
                except:
                    pass
            
            self._show_snackbar(f"🎉 ¡Todos los medicamentos completados! ({completados} medicamentos)")
            self.refresh_list()
            # No reabrir checklist automáticamente para evitar crashes
        else:
            self._show_snackbar("✅ Todos los medicamentos ya están completados")

    def mostrar_notificacion_compra(self, index, med, dias_restantes):
        """Muestra notificación para comprar medicamento"""
        self.play_notification_sound()
        
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        
        # Fondo con alto contraste - rojo oscuro para alertas
        from kivy.graphics import Color, Rectangle
        with content.canvas.before:
            Color(0.8, 0.2, 0.2, 1)  # Rojo oscuro
            Rectangle(pos=content.pos, size=content.size)
            Color(1, 0.95, 0.95, 1)  # Rosa muy claro para contenido
            Rectangle(pos=(content.x + dp(10), content.y + dp(10)), size=(content.width - dp(20), content.height - dp(20)))
        
        mensaje = f"⚠️ ¡ATENCIÓN!\n\nTu medicamento '{med['nombre']}' se acabará en {dias_restantes} días.\n\n¿Ya compraste más medicamento?"
        
        info_label = Label(
            text=mensaje,
            text_size=(dp(320), None),
            halign='center',
            color=(0.2, 0.2, 0.2, 1),
            font_size='16sp'
        )
        content.add_widget(info_label)
        
        buttons_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        
        btn_si = Button(
            text="✅ Sí, ya compré", 
            size_hint_x=0.5,
            background_color=(0.2, 0.7, 0.4, 1),
            color=(1, 1, 1, 1),
            font_size='14sp'
        )
        btn_no = Button(
            text="⏰ Recordar después", 
            size_hint_x=0.5,
            background_color=(0.7, 0.5, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='14sp'
        )
        
        popup = Popup(title="⚠️ Medicamento por agotarse", content=content, size_hint=(0.9, 0.6))
        
        btn_si.bind(on_release=lambda x: (popup.dismiss(), self.medicamento_comprado(index)))
        btn_no.bind(on_release=popup.dismiss)
        
        buttons_layout.add_widget(btn_si)
        buttons_layout.add_widget(btn_no)
        content.add_widget(buttons_layout)
        
        popup.open()

    def medicamento_comprado(self, index):
        """Maneja cuando el usuario confirma que compró el medicamento"""
        if 0 <= index < len(self.medicamentos):
            med = self.medicamentos[index]
            presentacion = med.get('presentacion', 'unidades').lower()
            
            # Determinar la unidad correcta
            if 'gramo' in presentacion or 'mg' in presentacion or 'kg' in presentacion:
                unidad = 'gramos'
            elif 'tableta' in presentacion or 'pastilla' in presentacion or 'capsula' in presentacion:
                unidad = 'tabletas'
            elif 'ml' in presentacion or 'litro' in presentacion:
                unidad = 'ml'
            else:
                unidad = 'unidades'
            
            content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
            
            # Fondo con alto contraste - verde oscuro para confirmaciones
            from kivy.graphics import Color, Rectangle
            with content.canvas.before:
                Color(0.2, 0.6, 0.2, 1)  # Verde oscuro
                Rectangle(pos=content.pos, size=content.size)
                Color(0.95, 1, 0.95, 1)  # Verde muy claro para contenido
                Rectangle(pos=(content.x + dp(10), content.y + dp(10)), size=(content.width - dp(20), content.height - dp(20)))
            
            info_label = Label(
                text=f"💊 ¿Cuántas {unidad} compraste de {med['nombre']}?",
                text_size=(dp(350), None),
                halign='center',
                color=(0.2, 0.2, 0.2, 1),
                font_size='16sp'
            )
            content.add_widget(info_label)
            
            cantidad_input = TextInput(
                hint_text=f"Cantidad en {unidad}",
                multiline=False,
                input_filter="float",
                size_hint_y=None,
                height=dp(45),
                background_color=(0.97, 0.98, 1, 1),
                foreground_color=(0.2, 0.2, 0.2, 1),
                cursor_color=(0.2, 0.6, 0.9, 1),
                font_size='16sp',
                padding=(dp(15), dp(12))
            )
            content.add_widget(cantidad_input)
            
            buttons_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
            
            btn_confirmar = Button(
                text="✅ Confirmar", 
                size_hint_x=0.5,
                background_color=(0.2, 0.7, 0.4, 1),
                color=(1, 1, 1, 1),
                font_size='14sp'
            )
            btn_cancelar = Button(
                text="❌ Cancelar", 
                size_hint_x=0.5,
                background_color=(0.6, 0.6, 0.6, 1),
                color=(1, 1, 1, 1),
                font_size='14sp'
            )
            
            popup = Popup(title=f"📦 Comprar {med['nombre']}", content=content, size_hint=(0.8, 0.5))
            
            btn_confirmar.bind(on_release=lambda x: self.actualizar_medicamento(index, cantidad_input.text, popup))
            btn_cancelar.bind(on_release=popup.dismiss)
            
            buttons_layout.add_widget(btn_confirmar)
            buttons_layout.add_widget(btn_cancelar)
            content.add_widget(buttons_layout)
            
            popup.open()
        else:
            self._show_snackbar("Error: Medicamento no encontrado")

    def actualizar_medicamento(self, index, nueva_cantidad_text, popup):
        """Actualiza la cantidad y recalcula la fecha de finalización"""
        try:
            nueva_cantidad = float(nueva_cantidad_text) if nueva_cantidad_text else 0
            if nueva_cantidad <= 0:
                self._show_snackbar("❌ Cantidad inválida")
                return
                
            med = self.medicamentos[index]
            
            # Calcular días restantes actuales
            dias_restantes_actuales = 0
            ahora = datetime.now()
            if med.get("fecha_fin"):
                try:
                    fecha_fin_original = datetime.strptime(med["fecha_fin"], "%Y-%m-%d %H:%M")
                    if fecha_fin_original > ahora:
                        dias_restantes_actuales = (fecha_fin_original - ahora).days
                except:
                    dias_restantes_actuales = 0
            
            # Calcular días que durará la nueva compra
            dias_nueva_compra = (nueva_cantidad / med["dosis"]) * med["frecuencia_dias"]
            
            # Sumar días totales
            dias_totales = dias_restantes_actuales + int(dias_nueva_compra)
            
            # Actualizar cantidad actual
            cantidad_restante_actual = med.get("cantidad_actual", 0)
            med["cantidad_actual"] = cantidad_restante_actual + nueva_cantidad
            
            # Calcular nueva fecha de finalización
            nueva_fecha_fin = ahora + timedelta(days=dias_totales)
            med["fecha_fin"] = nueva_fecha_fin.strftime("%Y-%m-%d %H:%M")
            med["notificaciones_activas"] = False  # Resetear notificaciones
            
            self.save_meds()
            self.refresh_list()
            
            popup.dismiss()
            
            # Mostrar información detallada
            presentacion = med.get('presentacion', 'unidades').lower()
            if 'gramo' in presentacion or 'mg' in presentacion or 'kg' in presentacion:
                unidad = 'gramos'
            elif 'tableta' in presentacion or 'pastilla' in presentacion or 'capsula' in presentacion:
                unidad = 'tabletas'
            elif 'ml' in presentacion or 'litro' in presentacion:
                unidad = 'ml'
            else:
                unidad = 'unidades'
            
            mensaje = f"✅ {med['nombre']} actualizado!\n"
            mensaje += f"📦 Agregaste: {nueva_cantidad} {unidad}\n"
            mensaje += f"⏰ Días adicionales: {int(dias_nueva_compra)}\n"
            mensaje += f"📅 Nueva fecha de fin: {nueva_fecha_fin.strftime('%d/%m/%Y')}\n"
            mensaje += f"📊 Total días restantes: {dias_totales}"
            
            self._show_snackbar(mensaje)
            
        except Exception as e:
            self._show_snackbar(f"❌ Error al actualizar medicamento: {str(e)}")

class TrackerApp(App):
    def build(self):
        screen_manager = Builder.load_file("tracker.kv")
        screen_manager.current = "login"
        return screen_manager


if __name__ == "__main__":
    TrackerApp().run()
