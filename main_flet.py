import flet as ft
from datetime import datetime, timedelta
import json
import os
import threading
import time
import asyncio

# Archivos de datos
USUARIO_FILE = "usuario.json"
MEDICAMENTOS_FILE = "medicamentos.json"
HISTORIAL_FILE = "historial_notificaciones.json"

class MedicationTrackerApp:
    def __init__(self):
        self.medicamentos = []
        self.historial_notificaciones = []
        self.usuario_actual = None
        self.notification_thread = None
        self.dose_reminder_thread = None
        self.stop_notifications = False
        
        # Cargar datos
        self.load_meds()
        self.cargar_historial()
        
    def load_meds(self):
        """Carga medicamentos desde archivo JSON"""
        try:
            if os.path.exists(MEDICAMENTOS_FILE):
                with open(MEDICAMENTOS_FILE, 'r', encoding='utf-8') as f:
                    self.medicamentos = json.load(f)
        except:
            self.medicamentos = []
    
    def save_meds(self):
        """Guarda medicamentos en archivo JSON"""
        try:
            with open(MEDICAMENTOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.medicamentos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando medicamentos: {e}")
    
    def cargar_historial(self):
        """Carga historial de notificaciones"""
        try:
            if os.path.exists(HISTORIAL_FILE):
                with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
                    self.historial_notificaciones = json.load(f)
        except:
            self.historial_notificaciones = []
    
    def save_historial(self):
        """Guarda historial de notificaciones"""
        try:
            with open(HISTORIAL_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.historial_notificaciones, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def calcular_fecha_fin(self, cantidad, dosis, frecuencia, inicio=None):
        """Calcula cuándo se acabará el medicamento"""
        if cantidad <= 0 or dosis <= 0 or frecuencia <= 0:
            return None
        
        dias_duracion = (cantidad / dosis) * frecuencia
        
        if inicio:
            try:
                fecha_inicio = datetime.strptime(inicio, "%Y-%m-%d %H:%M")
            except:
                fecha_inicio = datetime.now()
        else:
            fecha_inicio = datetime.now()
        
        fecha_fin = fecha_inicio + timedelta(days=dias_duracion)
        return fecha_fin.strftime("%Y-%m-%d %H:%M")
    
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

def main(page: ft.Page):
    page.title = "💊 Tracker de Medicamentos"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    page.bgcolor = ft.colors.BLUE_GREY_50
    
    # Instancia de la app
    app = MedicationTrackerApp()
    
    # Variables de estado
    current_view = ft.Ref[ft.View]()
    
    def show_snackbar(message, color=ft.colors.GREEN):
        """Muestra mensaje temporal"""
        page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(message, color=ft.colors.WHITE),
                bgcolor=color,
                duration=3000
            )
        )
    
    def get_urgency_color(dias_restantes):
        """Obtiene color según urgencia"""
        if isinstance(dias_restantes, str) and "días" in dias_restantes:
            try:
                dias_num = int(dias_restantes.split()[0])
                if dias_num <= 3:
                    return ft.colors.RED_100, ft.colors.RED_800
                elif dias_num <= 7:
                    return ft.colors.ORANGE_100, ft.colors.ORANGE_800
                else:
                    return ft.colors.GREEN_100, ft.colors.GREEN_800
            except:
                return ft.colors.GREY_100, ft.colors.GREY_800
        else:
            return ft.colors.BLUE_GREY_100, ft.colors.BLUE_GREY_800
    
    def refresh_medication_list():
        """Actualiza la lista de medicamentos"""
        medication_list.controls.clear()
        
        if not app.medicamentos:
            medication_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.MEDICATION, size=64, color=ft.colors.GREY_400),
                        ft.Text("No hay medicamentos registrados", 
                               size=16, color=ft.colors.GREY_600, text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=40,
                    alignment=ft.alignment.center
                )
            )
        else:
            for i, med in enumerate(app.medicamentos):
                dias_restantes = app.calcular_dias_restantes(med)
                bg_color, text_color = get_urgency_color(dias_restantes)
                
                # Crear card del medicamento
                med_card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.ListTile(
                                leading=ft.Icon(ft.icons.MEDICATION, color=text_color),
                                title=ft.Text(f"{med['nombre']}", weight=ft.FontWeight.BOLD, color=text_color),
                                subtitle=ft.Text(f"{med.get('descripcion', 'Sin descripción')}", color=text_color),
                                trailing=ft.PopupMenuButton(
                                    icon=ft.icons.MORE_VERT,
                                    items=[
                                        ft.PopupMenuItem(text="✏️ Editar", on_click=lambda e, idx=i: edit_medication(idx)),
                                        ft.PopupMenuItem(text="🗑️ Eliminar", on_click=lambda e, idx=i: delete_medication(idx)),
                                    ]
                                )
                            ),
                            ft.Divider(height=1),
                            ft.Container(
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(f"📦 {med['presentacion']}", size=12, color=text_color),
                                        ft.Text(f"💊 Dosis: {med['dosis']}", size=12, color=text_color),
                                    ], expand=True),
                                    ft.Column([
                                        ft.Text(f"📊 Cantidad: {med.get('cantidad_actual', med['cantidad_total'])}", size=12, color=text_color),
                                        ft.Text(f"⏰ Cada {med['frecuencia_dias']} días", size=12, color=text_color),
                                    ], expand=True),
                                    ft.Column([
                                        ft.Text("Se acaba en:", size=10, color=text_color),
                                        ft.Text(f"{dias_restantes}", size=12, weight=ft.FontWeight.BOLD, color=text_color),
                                    ], horizontal_alignment=ft.CrossAxisAlignment.END)
                                ]),
                                padding=ft.padding.all(10)
                            )
                        ]),
                        bgcolor=bg_color,
                        border_radius=8,
                        padding=5
                    ),
                    elevation=2,
                    margin=ft.margin.symmetric(vertical=4)
                )
                
                medication_list.controls.append(med_card)
        
        page.update()
    
    def add_medication(e):
        """Abre diálogo para agregar medicamento"""
        nombre_field = ft.TextField(label="Nombre del medicamento", autofocus=True)
        descripcion_field = ft.TextField(label="Descripción", multiline=True, max_lines=2)
        presentacion_dropdown = ft.Dropdown(
            label="Presentación",
            options=[
                ft.dropdown.Option("Tabletas"),
                ft.dropdown.Option("Cápsulas"),
                ft.dropdown.Option("Jarabe"),
                ft.dropdown.Option("Gotas"),
                ft.dropdown.Option("Ampolletas"),
                ft.dropdown.Option("Crema"),
                ft.dropdown.Option("Gel"),
                ft.dropdown.Option("Spray"),
            ]
        )
        cantidad_field = ft.TextField(label="Cantidad total", keyboard_type=ft.KeyboardType.NUMBER)
        dosis_field = ft.TextField(label="Dosis por toma", keyboard_type=ft.KeyboardType.NUMBER)
        frecuencia_field = ft.TextField(label="Frecuencia (días)", keyboard_type=ft.KeyboardType.NUMBER)
        
        def save_medication(e):
            try:
                nuevo_med = {
                    "nombre": nombre_field.value,
                    "descripcion": descripcion_field.value or "",
                    "presentacion": presentacion_dropdown.value,
                    "cantidad_total": float(cantidad_field.value),
                    "cantidad_actual": float(cantidad_field.value),
                    "dosis": float(dosis_field.value),
                    "frecuencia_dias": int(frecuencia_field.value),
                    "fecha_inicio": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "notificaciones_activas": False
                }
                
                # Calcular fecha de finalización
                nuevo_med["fecha_fin"] = app.calcular_fecha_fin(
                    nuevo_med["cantidad_total"],
                    nuevo_med["dosis"],
                    nuevo_med["frecuencia_dias"]
                )
                
                app.medicamentos.append(nuevo_med)
                app.save_meds()
                refresh_medication_list()
                show_snackbar("✅ Medicamento agregado correctamente")
                page.close(dlg)
                
            except Exception as ex:
                show_snackbar(f"❌ Error: {str(ex)}", ft.colors.RED)
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("💊 Agregar Medicamento"),
            content=ft.Container(
                content=ft.Column([
                    nombre_field,
                    descripcion_field,
                    presentacion_dropdown,
                    cantidad_field,
                    dosis_field,
                    frecuencia_field,
                ], tight=True),
                width=400,
                height=400
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("💾 Guardar", on_click=save_medication),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dlg)
    
    def edit_medication(index):
        """Edita un medicamento existente"""
        med = app.medicamentos[index]
        
        nombre_field = ft.TextField(label="Nombre del medicamento", value=med['nombre'])
        descripcion_field = ft.TextField(label="Descripción", value=med.get('descripcion', ''), multiline=True, max_lines=2)
        presentacion_dropdown = ft.Dropdown(
            label="Presentación",
            value=med['presentacion'],
            options=[
                ft.dropdown.Option("Tabletas"),
                ft.dropdown.Option("Cápsulas"),
                ft.dropdown.Option("Jarabe"),
                ft.dropdown.Option("Gotas"),
                ft.dropdown.Option("Ampolletas"),
                ft.dropdown.Option("Crema"),
                ft.dropdown.Option("Gel"),
                ft.dropdown.Option("Spray"),
            ]
        )
        cantidad_field = ft.TextField(label="Cantidad actual", value=str(med.get('cantidad_actual', med['cantidad_total'])), keyboard_type=ft.KeyboardType.NUMBER)
        dosis_field = ft.TextField(label="Dosis por toma", value=str(med['dosis']), keyboard_type=ft.KeyboardType.NUMBER)
        frecuencia_field = ft.TextField(label="Frecuencia (días)", value=str(med['frecuencia_dias']), keyboard_type=ft.KeyboardType.NUMBER)
        
        def update_medication(e):
            try:
                app.medicamentos[index].update({
                    "nombre": nombre_field.value,
                    "descripcion": descripcion_field.value or "",
                    "presentacion": presentacion_dropdown.value,
                    "cantidad_actual": float(cantidad_field.value),
                    "dosis": float(dosis_field.value),
                    "frecuencia_dias": int(frecuencia_field.value),
                })
                
                # Recalcular fecha de finalización
                app.medicamentos[index]["fecha_fin"] = app.calcular_fecha_fin(
                    float(cantidad_field.value),
                    float(dosis_field.value),
                    int(frecuencia_field.value),
                    app.medicamentos[index].get("fecha_inicio")
                )
                
                app.save_meds()
                refresh_medication_list()
                show_snackbar("✅ Medicamento actualizado")
                page.close(dlg)
                
            except Exception as ex:
                show_snackbar(f"❌ Error: {str(ex)}", ft.colors.RED)
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("✏️ Editar Medicamento"),
            content=ft.Container(
                content=ft.Column([
                    nombre_field,
                    descripcion_field,
                    presentacion_dropdown,
                    cantidad_field,
                    dosis_field,
                    frecuencia_field,
                ], tight=True),
                width=400,
                height=400
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("💾 Actualizar", on_click=update_medication),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dlg)
    
    def delete_medication(index):
        """Elimina un medicamento"""
        med = app.medicamentos[index]
        
        def confirm_delete(e):
            app.medicamentos.pop(index)
            app.save_meds()
            refresh_medication_list()
            show_snackbar("🗑️ Medicamento eliminado")
            page.close(dlg)
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("🗑️ Eliminar Medicamento"),
            content=ft.Text(f"¿Estás seguro de eliminar '{med['nombre']}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("🗑️ Eliminar", on_click=confirm_delete, bgcolor=ft.colors.RED, color=ft.colors.WHITE),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dlg)
    
    def show_statistics(e):
        """Muestra estadísticas de medicamentos"""
        if not app.medicamentos:
            show_snackbar("📭 No hay medicamentos para mostrar estadísticas", ft.colors.ORANGE)
            return
        
        # Calcular estadísticas
        total_meds = len(app.medicamentos)
        meds_activos = len([m for m in app.medicamentos if app.calcular_dias_restantes(m) != "¡AGOTADO!"])
        meds_agotados = total_meds - meds_activos
        
        # Crear gráficas de duración
        duration_charts = []
        for med in app.medicamentos:
            dias_restantes = app.calcular_dias_restantes(med)
            bg_color, text_color = get_urgency_color(dias_restantes)
            
            if isinstance(dias_restantes, str) and "días" in dias_restantes:
                try:
                    dias_num = int(dias_restantes.split()[0])
                    progress = min(dias_num / 30, 1.0)  # Máximo 30 días
                except:
                    progress = 0
            else:
                progress = 0
            
            duration_charts.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"💊 {med['nombre']}", weight=ft.FontWeight.BOLD),
                        ft.ProgressBar(value=progress, color=text_color, bgcolor=ft.colors.GREY_300),
                        ft.Text(f"{dias_restantes}", size=12, color=text_color)
                    ]),
                    padding=10,
                    margin=5,
                    bgcolor=bg_color,
                    border_radius=8
                )
            )
        
        # Calcular promedios
        duraciones = []
        for med in app.medicamentos:
            if med.get('fecha_inicio') and med.get('fecha_fin'):
                try:
                    inicio = datetime.strptime(med['fecha_inicio'], "%Y-%m-%d %H:%M")
                    fin = datetime.strptime(med['fecha_fin'], "%Y-%m-%d %H:%M")
                    duracion = (fin - inicio).days
                    if duracion > 0:
                        duraciones.append(duracion)
                except:
                    continue
        
        stats_content = ft.Column([
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("📈 RESUMEN GENERAL", size=18, weight=ft.FontWeight.BOLD),
                        ft.Divider(),
                        ft.Row([
                            ft.Column([
                                ft.Text(f"{total_meds}", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE),
                                ft.Text("Total", size=12)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([
                                ft.Text(f"{meds_activos}", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN),
                                ft.Text("Activos", size=12)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([
                                ft.Text(f"{meds_agotados}", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.RED),
                                ft.Text("Agotados", size=12)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
                    ]),
                    padding=20
                )
            ),
            ft.Text("📊 DURACIÓN DE MEDICAMENTOS", size=16, weight=ft.FontWeight.BOLD),
            ft.Column(duration_charts, scroll=ft.ScrollMode.AUTO, height=200),
        ])
        
        if duraciones:
            promedio = sum(duraciones) / len(duraciones)
            stats_content.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("📈 ANÁLISIS DE CONSUMO", size=16, weight=ft.FontWeight.BOLD),
                            ft.Divider(),
                            ft.Text(f"• Duración promedio: {promedio:.1f} días"),
                            ft.Text(f"• Duración máxima: {max(duraciones)} días"),
                            ft.Text(f"• Duración mínima: {min(duraciones)} días"),
                            ft.Text(f"• Medicamentos analizados: {len(duraciones)}"),
                        ]),
                        padding=20
                    )
                )
            )
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("📊 Estadísticas"),
            content=ft.Container(
                content=stats_content,
                width=500,
                height=600
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg)),
            ],
        )
        
        page.open(dlg)
    
    def show_calendar(e):
        """Muestra calendario de medicamentos"""
        hoy = datetime.now()
        calendar_content = ft.Column([
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"🗓️ HOY - {hoy.strftime('%d/%m/%Y')}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Divider(),
                    ]),
                    padding=15
                ),
                bgcolor=ft.colors.BLUE_50
            )
        ])
        
        # Medicamentos de hoy
        medicamentos_hoy = []
        for med in app.medicamentos:
            if es_dia_de_toma(med, hoy):
                medicamentos_hoy.append(med)
        
        if medicamentos_hoy:
            for med in medicamentos_hoy:
                calendar_content.controls.append(
                    ft.Card(
                        content=ft.ListTile(
                            leading=ft.Icon(ft.icons.MEDICATION, color=ft.colors.GREEN),
                            title=ft.Text(f"{med['nombre']}"),
                            subtitle=ft.Text(f"Dosis: {med['dosis']}"),
                        ),
                        bgcolor=ft.colors.GREEN_50
                    )
                )
        else:
            calendar_content.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Text("✅ No hay medicamentos programados para hoy", 
                                       color=ft.colors.GREY_600),
                        padding=15
                    )
                )
            )
        
        # Próximos 7 días
        calendar_content.controls.append(
            ft.Text("📋 PRÓXIMOS 7 DÍAS", size=16, weight=ft.FontWeight.BOLD)
        )
        
        for i in range(1, 8):
            fecha = hoy + timedelta(days=i)
            dia_nombre = fecha.strftime('%A')
            fecha_str = fecha.strftime('%d/%m')
            
            medicamentos_dia = []
            for med in app.medicamentos:
                if es_dia_de_toma(med, fecha):
                    medicamentos_dia.append(med)
            
            day_card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"📆 {dia_nombre.capitalize()} {fecha_str}", weight=ft.FontWeight.BOLD),
                        ft.Divider(height=1),
                    ]),
                    padding=10
                )
            )
            
            if medicamentos_dia:
                for med in medicamentos_dia:
                    day_card.content.content.controls.append(
                        ft.Text(f"  💊 {med['nombre']} ({med['dosis']})", size=12)
                    )
            else:
                day_card.content.content.controls.append(
                    ft.Text("  ✅ Sin medicamentos", size=12, color=ft.colors.GREY_600)
                )
            
            calendar_content.controls.append(day_card)
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("📅 Calendario"),
            content=ft.Container(
                content=ft.Column(calendar_content.controls, scroll=ft.ScrollMode.AUTO),
                width=500,
                height=600
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg)),
            ],
        )
        
        page.open(dlg)
    
    def es_dia_de_toma(medicamento, fecha):
        """Determina si un medicamento debe tomarse en una fecha específica"""
        if not medicamento.get('fecha_inicio'):
            return False
        
        try:
            inicio = datetime.strptime(medicamento['fecha_inicio'], "%Y-%m-%d %H:%M")
            frecuencia = int(medicamento.get('frecuencia_dias', 1))
            
            dias_desde_inicio = (fecha.date() - inicio.date()).days
            return dias_desde_inicio >= 0 and dias_desde_inicio % frecuencia == 0
        except:
            return False
    
    def show_history(e):
        """Muestra historial de notificaciones"""
        history_content = ft.Column([])
        
        if not app.historial_notificaciones:
            history_content.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.HISTORY, size=64, color=ft.colors.GREY_400),
                        ft.Text("No hay notificaciones en el historial", 
                               color=ft.colors.GREY_600, text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=40,
                    alignment=ft.alignment.center
                )
            )
        else:
            for notif in reversed(app.historial_notificaciones[-20:]):
                if notif['tipo'] == 'dosis':
                    icon = ft.icons.MEDICATION
                    color = ft.colors.GREEN
                elif notif['tipo'] == 'stock_bajo':
                    icon = ft.icons.WARNING
                    color = ft.colors.ORANGE
                else:
                    icon = ft.icons.ERROR
                    color = ft.colors.RED
                
                history_content.controls.append(
                    ft.Card(
                        content=ft.ListTile(
                            leading=ft.Icon(icon, color=color),
                            title=ft.Text(notif['medicamento']),
                            subtitle=ft.Text(f"{notif['mensaje']}\n🕐 {notif['fecha']}", size=12),
                        )
                    )
                )
        
        def clear_history(e):
            app.historial_notificaciones = []
            app.save_historial()
            show_snackbar("🗑️ Historial limpiado")
            page.close(dlg)
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("📋 Historial"),
            content=ft.Container(
                content=ft.Column(history_content.controls, scroll=ft.ScrollMode.AUTO),
                width=500,
                height=600
            ),
            actions=[
                ft.TextButton("🗑️ Limpiar", on_click=clear_history),
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg)),
            ],
        )
        
        page.open(dlg)
    
    # Lista de medicamentos
    medication_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)
    
    # Barra de aplicación
    app_bar = ft.AppBar(
        leading=ft.Icon(ft.icons.MEDICATION),
        leading_width=40,
        title=ft.Text("💊 Tracker de Medicamentos", size=20, weight=ft.FontWeight.BOLD),
        center_title=False,
        bgcolor=ft.colors.BLUE_600,
        color=ft.colors.WHITE,
        actions=[
            ft.IconButton(
                icon=ft.icons.ANALYTICS,
                tooltip="Estadísticas",
                on_click=show_statistics,
                icon_color=ft.colors.WHITE
            ),
            ft.IconButton(
                icon=ft.icons.CALENDAR_TODAY,
                tooltip="Calendario",
                on_click=show_calendar,
                icon_color=ft.colors.WHITE
            ),
            ft.IconButton(
                icon=ft.icons.HISTORY,
                tooltip="Historial",
                on_click=show_history,
                icon_color=ft.colors.WHITE
            ),
        ],
    )
    
    # Botón flotante para agregar
    fab = ft.FloatingActionButton(
        icon=ft.icons.ADD,
        tooltip="Agregar medicamento",
        on_click=add_medication,
        bgcolor=ft.colors.BLUE_600,
        foreground_color=ft.colors.WHITE
    )
    
    # Layout principal
    page.add(
        ft.Column([
            app_bar,
            ft.Container(
                content=medication_list,
                padding=10,
                expand=True
            )
        ], expand=True)
    )
    
    page.floating_action_button = fab
    
    # Cargar medicamentos iniciales
    refresh_medication_list()

if __name__ == "__main__":
    ft.app(target=main, port=8080, view=ft.AppView.WEB_BROWSER)
