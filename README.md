# 💊 Tracker de Medicamentos

Una aplicación móvil para Android que te ayuda a gestionar y recordar tus medicamentos de forma inteligente.

## 🌟 Características

### 📋 Gestión de Medicamentos
- Registro completo de medicamentos con nombre, descripción, dosis y frecuencia
- Cálculo automático de fechas de finalización
- Seguimiento de cantidades restantes
- Codificación por colores según urgencia

### 🔔 Sistema de Notificaciones Inteligente
- **Recordatorios de dosis**: Alertas automáticas cuando es hora de tomar medicamentos
- **Alertas de stock bajo**: Notificaciones cuando quedan 3 días o menos
- **Sonidos y vibración**: Alertas audibles y táctiles en Android
- **Historial completo**: Registro de todas las notificaciones

### 🎨 Diseño Accesible
- Paleta de colores cálida y profesional
- Contraste optimizado (WCAG 4.5:1)
- Interfaz intuitiva con emojis identificativos
- Diseño responsive para móviles

### 📱 Funcionalidades Móviles
- Optimizado para Android
- Vibración en notificaciones importantes
- Interfaz táctil amigable
- Almacenamiento local seguro

## 🚀 Instalación para Desarrollo

### Requisitos
- Python 3.8+
- Kivy 2.3.1
- Buildozer (para compilar APK)

### Configuración
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar en desarrollo
python main.py

# Compilar para Android
buildozer android debug
```

## 📦 Compilar APK

Para generar el archivo APK para Android:

```bash
# Instalar buildozer
pip install buildozer

# Compilar APK de debug
buildozer android debug

# Compilar APK de release (para Play Store)
buildozer android release
```

## 🏪 Preparación para Google Play Store

### Archivos necesarios:
1. **APK firmado** (`bin/medicamentostracker-1.0-arm64-v8a-release.apk`)
2. **Íconos de la app** (512x512 px)
3. **Screenshots** (mínimo 2, máximo 8)
4. **Descripción de la app**
5. **Política de privacidad**

### Información de la App:
- **Nombre**: Tracker de Medicamentos
- **Categoría**: Medicina
- **Clasificación**: Para todas las edades
- **Permisos**: Almacenamiento, Vibración

## 🔒 Privacidad y Seguridad

- Todos los datos se almacenan localmente en el dispositivo
- No se envía información a servidores externos
- Sin recolección de datos personales
- Cumple con regulaciones de privacidad

## 📋 Funcionalidades Principales

### Gestión de Medicamentos
- ➕ Agregar medicamentos con información completa
- ✏️ Editar medicamentos existentes
- 🗑️ Eliminar medicamentos
- 📊 Visualización de cantidades y fechas

### Sistema de Recordatorios
- ⏰ Recordatorios automáticos de dosis
- 📅 Cálculo inteligente de horarios
- 🔔 Notificaciones personalizables
- 📋 Historial de todas las alertas

### Interfaz de Usuario
- 🎨 Colores codificados por urgencia
- 📱 Diseño optimizado para móviles
- ♿ Accesibilidad mejorada
- 🌟 Experiencia de usuario intuitiva

## 🛠️ Tecnologías Utilizadas

- **Python 3**: Lenguaje principal
- **Kivy**: Framework de interfaz multiplataforma
- **Plyer**: Acceso a funciones nativas del dispositivo
- **Buildozer**: Herramienta de compilación para Android
- **JSON**: Almacenamiento de datos local

## 📞 Soporte

Para reportar problemas o sugerir mejoras, contacta al desarrollador.

## 📄 Licencia

Esta aplicación está desarrollada para uso personal y educativo.

---

**Versión**: 1.0  
**Plataforma**: Android 5.0+ (API 21+)  
**Tamaño**: ~15 MB  
**Desarrollado con**: ❤️ y Python
