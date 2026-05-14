"""
Скворечник в голландском стиле, для FDM-печати из PETG.

Архитектура (3 детали):
  1. base       — монолит: пол + 4 стенки + 2 фронтона с плоскими пиками
                  + штыри Ø3.5 на пиках для замкового соединения с крышей
                  + леток-«домик» + декор (фахверк, рамка летка)
                  + keyhole-слоты в задней стенке для подвеса
                  + дренаж в полу + вентиляция в боковинах
                  Печатается СТОЯ, дном на стол, без поддержек.
  2. roof_half  — скат с черепичной текстурой и 2 ПОЛУКРУГЛЫМИ ВЫЕМКАМИ Ø4.5
                  на коньковом крае. Печатается плашмя, 2 копии.
  3. tree_mount — настенная плата с 2 грибовидными штырями, садящимися в
                  keyhole-слоты задней стенки. Прикручивается 4 саморезами.

Замок крыши на базу:
  • на верхушке каждой боковой стенки — продольный паз (6×6 мм)
    с утолщением стенки внутрь на 5 мм (чтобы паз не ослаблял конструкцию)
  • на нижней стороне каждого ската — продольный шип (3×3 мм)
  • при сборке шипы опускаются в пазы — крыша зафиксирована от сноса
  • большой клиренс (по 1.5 мм с каждой стороны от шипа) — войдёт даже
    с погрешностями печати, и есть место для герметика
  • МИТРОВАЯ ПОДРЕЗКА коньковой кромки ската: вертикальный (в сборке) срез,
    после которого две наружные грани встречаются точно на линии конька
    Z=GABLE_PEAK_Z. Без подрезки скаты с прямоугольным сечением «прятали»
    наружную грань внутрь конька на ROOF_T*cos(a) — получалась щель.
  • после сборки пользователь промазывает швы силиконом — крыша герметична
  • резервная проволочная стяжка через Ø3-отверстия в фронтонах и скатах

Для печати скатов: roof_half.stl печатается 2 раза. Для ПРАВОГО ската
поверни его в слайсере (mirror по длинной оси / по X) — ребро тогда смотрит
на правый паз. В сборочной превью это сделано через `mirror("YZ")`.
"""
from __future__ import annotations
import math
from pathlib import Path
import cadquery as cq

# ============================================================
# ВЕРСИЯ ПРОЕКТА
# ============================================================
# v18: настоящий фикс конька — митровая подрезка кромки ската + перенос сборки так,
#      чтобы НАРУЖНЫЕ грани скатов встречались по линии конька на Z=GABLE_PEAK_Z.
#      Раньше переносили по внутренней кромке (max(X) панели после поворота), отчего
#      наружные грани не доставали до пика фронтона на ROOF_T*cos(a)≈3 мм — получался
#      треугольный жёлоб вдоль всего конька. Также правый скат теперь зеркало левого,
#      а не "тот же поворот в другую сторону" — раньше его ребро уходило на X≈+81
#      вместо паза +65. ridge_cap_patch удалён как симптоматический патч.
VERSION = 18

# ============================================================
# ПАРАМЕТРЫ
# ============================================================

# --- Принтер / материал ---
TOL = 0.5            # slip-fit для PETG (учёт усадки и точности FDM)

# --- Габариты ---
EXT = 140.0          # внешняя ширина и глубина (квадратное основание)
WALL_H = 195.0       # высота прямоугольной части стенок (v13: было 160 — слишком низко для летка)
GABLE_H = 45.0       # высота фронтона (v13: было 56 — уменьшено чтобы влезло в стол 250 мм)
WALL_T = 6.0         # толщина стенок (v13: было 4 — увеличено для теплоизоляции в жару)
FLOOR_T = 6.0        # толщина пола (для пирамидального дренажа: центр пола 3 мм после депрессии)
ROOF_T = 3.5         # v15: тоньше (было 5) — экономия материала и времени печати

# --- Леток (пятиугольник «домик» — без моста при печати) ---
ENT_W = 32.0          # ширина прямоугольной части
ENT_RECT_H = 22.0     # высота прямоугольной части
ENT_PEAK_H = 14.0     # высота треугольного пика
ENT_Z_BASE = 130.0    # высота нижнего края от внутреннего пола (v13: было 95 — поднято для правильных пропорций)

# --- Соединение крыши с базой (шип-в-пазу по периметру боковин) ---
# На верхушке каждой боковины делается продольный паз с генерируемым клиренсом.
# Скат имеет соответствующий шип на нижней стороне, который опускается в паз.
# Конструкция надёжна и герметизируется силиконом по факту установки.
# Дополнительно фронтоны имеют плоскую площадку 8 мм на коньке — чтобы не было
# острого угла (важно для манифольдной геометрии и стабильной печати).
GABLE_FLAT_W = 8.0           # ширина плоской площадки на пике фронтона

# Lip — треугольное сечение (НАКЛОННАЯ нижняя грань → нет горизонтального overhang)
# Slope ratio = LIP_W / LIP_H. Должно быть ≤ 1.0 для печати без поддержек.
# 6/10 = 0.6 → угол 31° от вертикали → запас от 45° лимита FDM ✓
WALL_TOP_LIP_W = 6.0         # на сколько lip уходит ВНУТРЬ дома сверху (по X)
WALL_TOP_LIP_H = 18.0        # высота lip'а (наклон 6/18 = 18° от вертикали → надёжно без поддержек)
                             # 18 нужно чтобы при глубине паза 5 мм его внутренняя стенка
                             # лежала внутри наклонной грани lip'а с запасом 0.3+ мм

ROOF_GROOVE_W = 6.0          # ширина паза (X) — больше чем X-проекция ребра 5.08 мм с запасом
ROOF_GROOVE_D = 5.0          # глубина паза (Z)
ROOF_GROOVE_MARGIN = 8.0     # отступ паза от концов боковины (избегаем фронтонов)

ROOF_RIB_W = 2.5             # ширина ребра ската (вдоль склона)
ROOF_RIB_H = 5.0             # высота ребра (перпендикулярно скату)
ROOF_RIB_LEN_MARGIN = 10.0   # ребро короче паза, удобнее опустить
ROOF_TIE_HOLE_D = 3.0        # резервная стяжка проволокой

# --- Крыша ---
ROOF_OVERHANG = 22.0  # вылет крыши за карниз/фронтон
# v15: текстура «черепицы» удалена (TILE_*) — крыша теперь гладкая

# --- Декор на стенках (фахверк — горизонтальные планки-канавки) ---
DECO_STRIP_Z = [50.0, 130.0]  # высоты центров планок (от внутреннего пола)
DECO_STRIP_H = 5.0
DECO_STRIP_D = 1.0    # глубина канавки

# --- Вентиляция (в боковинах, под карнизом) ---
VENT_W = 4.0
VENT_H = 16.0
N_VENT = 3

# --- Дренаж: пирамидальная выемка пола + центральный слив ---
# Внутренняя поверхность пола — квадратная пирамида с вершиной в центре (низшая точка).
# Вода с любого места стекает к центру. Печатается БЕЗ поддержек —
# каждый верхний слой меньше предыдущего (нет overhang).
DRAIN_PYRAMID_BASE = 132.0     # = размер полости (пирамида покрывает всё дно)
DRAIN_DEPRESSION = 3.0          # глубина пирамиды (вершина в центре)
DRAIN_D = 6.0                   # диаметр центрального сливного отверстия
SIDE_DRAIN_D = 5.0              # v14: диаметр боковых дренажей (резерв если центр засорится)
SIDE_DRAIN_OFFSET = 55.0        # v14: смещение от центра — на полпути к стенкам

# --- Гравировка-паттерн "MARK MARK MARK ..." на ВСЁМ дне (множество параллельных строк) ---
# Тонкие мелкие строки повторяются через пробел и идут параллельными диагональными
# полосами под 60° от горизонтали, заполняя всю площадь дна.
BOTTOM_TEXT_UNIT = "MARK "            # повторяющийся юнит (с пробелом)
BOTTOM_TEXT_REPEAT = 10               # сколько раз повторить юнит в одной строке (длина строки ≈ 300 мм)
BOTTOM_TEXT_SIZE = 9.0                # высота букв
BOTTOM_TEXT_DEPTH = 0.5               # глубина гравировки
BOTTOM_TEXT_ANGLE = 60.0              # угол строк от горизонтали (X-оси) в градусах
BOTTOM_TEXT_N_LINES = 17              # количество параллельных строк
BOTTOM_TEXT_LINE_SPACING = 12.0       # расстояние между центрами строк, мм
BOTTOM_TEXT_FONT = "Arial"

# --- Жёрдочка УДАЛЕНА в v13 (опасно для птиц — помогает хищникам забираться к гнезду) ---

# --- Внутренняя текстура для лазания (горизонтальные канавки на внутренней грани передней стенки) ---
# Птенцы используют их как ступеньки чтобы вылезти к летку.
# Без них пластик гладкий — птенцы соскальзывают.
CLIMB_GROOVE_DEPTH = 0.7       # глубина каждого паза в материал стенки
CLIMB_GROOVE_H = 1.2           # высота одного паза (тонкая горизонтальная линия)
CLIMB_GROOVE_SPACING = 8.0     # шаг между пазами по вертикали
CLIMB_Z_START = 15.0           # от внутреннего пола, начало текстуры (оставляем место для гнезда)
CLIMB_Z_BELOW_ENT = 5.0        # отступ от низа летка

# --- Keyhole-крепления в задней стенке (3-точечное: 2 сверху + 1 снизу = треугольник) ---
KH_BIG_D = 10.0       # ø для шляпки самореза (~ M4 / 8 PB / DIN 7981)
KH_SLOT_W = 4.5       # ширина щели для шейки
KH_SLOT_LEN = 14.0    # длина щели вниз
KH_X_TOP = 25.0       # горизонтальное смещение верхних keyhole'ов от центра
KH_Z_TOP = 130.0      # высота верхних keyhole'ов от внутреннего пола (2 шт.)
KH_Z_BOT = 50.0       # высота нижнего keyhole от внутреннего пола (1 шт., по центру X)

# --- Монтажная плата (Tree Mount Plate, TMP) — крепится на дерево/стену саморезами,
#     скворечник навешивается через 3-точечный треугольник: 2 штыря сверху + 1 снизу. ---
TMP_W = 80.0
TMP_H = 120.0
TMP_T = 5.0

# Расположение 3 грибовидных штырей (в координатах платы, центрированы)
# Шаг по вертикали между верхними и нижним = KH_Z_TOP - KH_Z_BOT = 80 мм (соответствует keyhole'ам)
TMP_PIN_X_TOP = 25.0       # = KH_X_TOP — горизонтальное смещение верхних штырей
TMP_PIN_Y_TOP = 40.0       # вертикальное положение верхних штырей (Y в плате)
TMP_PIN_Y_BOT = -40.0      # вертикальное положение нижнего штыря (= TMP_PIN_Y_TOP - 80 = -40)

# Грибовидный штырь: стебель + чамфер 45° + шляпка.
# Стебель < KH_SLOT_W=4.5; шляпка > KH_SLOT_W и < KH_BIG_D=10
TMP_PIN_STEM_D = 3.5
TMP_PIN_STEM_H = 8.0          # v18: было 5.5 — короче стенки 6 мм + клиренс 1 мм → шляпка
                              # утопала в стенке и не цеплялась за щель надёжно
TMP_PIN_HEAD_D = 8.0
TMP_PIN_HEAD_H = 3.0

# Саморезы в дерево (4 шт., в углах платы)
TMP_SCREW_D = 5.0
TMP_SCREW_HEAD_D = 9.5
TMP_SCREW_HEAD_DEPTH = 2.5
TMP_SCREW_DX = 32.0        # X-смещение от оси (от края 8 мм при TMP_W=80)
TMP_SCREW_DY = 52.0        # Y-смещение от оси (от края 8 мм при TMP_H=120)

# --- Производные значения ---
GABLE_PEAK_Z = FLOOR_T + WALL_H + GABLE_H  # абс. высота пика
EAVE_Z = FLOOR_T + WALL_H                  # абс. высота карниза
ROOF_RUN = EXT / 2.0
ROOF_ANGLE = math.atan2(GABLE_H, ROOF_RUN)
# v16 FIX: правильная длина ската по наклонной — это hypot(RUN, GABLE_H) для секции
# от конька до карниза, плюс OVERHANG/cos для секции свеса. Старая формула давала
# ~5 мм лишних, отчего скаты при сборке упирались друг в друга на коньке и поднимались
# с уплотнением в пазах → образовывалась щель. Не влияет на уже отпечатанные v15 детали,
# но фикс пригодится при следующей печати.
ROOF_SLOPE_LEN = math.hypot(ROOF_RUN, GABLE_H) + ROOF_OVERHANG / math.cos(ROOF_ANGLE)
ROOF_PANEL_Y = EXT + 2 * ROOF_OVERHANG     # длина ската вдоль конька


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ГЕОМЕТРИИ
# ============================================================
def entrance_profile() -> list[tuple[float, float]]:
    """Контур летка в форме «домика» (без моста при печати)."""
    w = ENT_W / 2
    h_rect = ENT_RECT_H
    h_peak = ENT_PEAK_H
    return [
        (-w, 0),
        ( w, 0),
        ( w, h_rect),
        ( 0, h_rect + h_peak),
        (-w, h_rect),
    ]


def dormer_profile() -> list[tuple[float, float]]:
    """Контур декоративного навеса в плоскости фронтона (XZ)."""
    w = DORMER_W / 2
    h = DORMER_PEAK_H
    return [
        (-w, 0),
        ( w, 0),
        ( 0, h),
    ]


# ============================================================
# 1. БАЗА — монолит
# ============================================================
def make_base() -> cq.Workplane:
    # --- Внешний коробчатый объём (пол + 4 стенки до карниза) ---
    outer_lower = cq.Workplane("XY").box(EXT, EXT, FLOOR_T + WALL_H) \
        .translate((0, 0, (FLOOR_T + WALL_H) / 2))

    # Полость (вычитаем выше пола)
    cav_w = EXT - 2 * WALL_T
    cavity = cq.Workplane("XY").box(cav_w, cav_w, WALL_H + 2) \
        .translate((0, 0, FLOOR_T + WALL_H / 2 + 1))
    base = outer_lower.cut(cavity)

    # --- Фронтоны (передний и задний), треугольные ---
    base = base.union(_make_gable(y_outer=-EXT / 2))
    base = base.union(_make_gable(y_outer=+EXT / 2))

    # --- Леток в передней стенке ---
    base = base.cut(_make_entrance_cutter())

    # --- Декоративная "рамка" вокруг летка (engraving — без overhang при печати) ---
    for g in _make_window_frame_grooves():
        base = base.cut(g)

    # --- Вентиляционные щели в боковинах ---
    for v in _make_vent_cutters():
        base = base.cut(v)

    # --- Дренаж в полу ---
    for d in _make_drain_cutters():
        base = base.cut(d)

    # --- Гравировка-паттерн "MARK MARK ..." на всей нижней грани пола ---
    for line_cutter in _make_bottom_text_lines():
        base = base.cut(line_cutter)

    # --- Внутренняя климб-текстура (горизонтальные канавки на передней стенке под летком) ---
    for groove in _make_climb_grooves():
        base = base.cut(groove)

    # --- Keyhole в задней стенке ---
    for kh in _make_keyhole_cutters():
        base = base.cut(kh)

    # --- Декор-фахверк (горизонтальные канавки на стенках) ---
    for g in _make_deco_grooves():
        base = base.cut(g)

    # --- Отверстия в пиках фронтонов для проволочной стяжки (резерв на случай ветра) ---
    for tie in _make_tie_holes():
        base = base.cut(tie)

    # --- Утолщение боковин сверху (под паз для крыши) ---
    base = base.union(_make_wall_top_lip(x_outer=-EXT / 2))
    base = base.union(_make_wall_top_lip(x_outer=+EXT / 2))

    # --- Пазы на верхушках боковин (главный замок крыши) ---
    base = base.cut(_make_roof_groove(x_outer=-EXT / 2))
    base = base.cut(_make_roof_groove(x_outer=+EXT / 2))

    return base


def _make_gable(y_outer: float) -> cq.Workplane:
    """Фронтон с ПЛОСКИМ верхом (не острый угол) — чтобы штырь крепления крыши
    садился на материал, а не висел над пустотой (non-manifold)."""
    pts = [
        (-EXT / 2, EAVE_Z),
        ( EXT / 2, EAVE_Z),
        ( GABLE_FLAT_W / 2, GABLE_PEAK_Z),
        (-GABLE_FLAT_W / 2, GABLE_PEAK_Z),
    ]
    sgn = -1.0 if y_outer < 0 else 1.0
    profile = cq.Workplane("XZ").polyline(pts).close()
    gable = profile.extrude(WALL_T if sgn > 0 else -WALL_T)
    gable = gable.translate((0, y_outer, 0))
    return gable


def _make_wall_top_lip(x_outer: float) -> cq.Workplane:
    """Утолщение на верхушке боковины с НАКЛОННОЙ нижней гранью.
    Сечение — прямоугольный треугольник в XZ:
       вершина 1: (inner_face, EAVE_Z)              — у внутренней грани стенки сверху
       вершина 2: (lip_inner_edge, EAVE_Z)          — внутренний край lip'а сверху
       вершина 3: (inner_face, EAVE_Z - WALL_TOP_LIP_H) — обратно к стенке внизу

    Наклонная нижняя грань (slope = LIP_W/LIP_H = 0.6 → 31° от вертикали)
    самонесущая для FDM (≤ 45°), не требует поддержек."""
    sgn = -1.0 if x_outer < 0 else 1.0
    inner_face = x_outer - sgn * WALL_T              # ±64 при WALL_T=6
    lip_inner_edge = inner_face - sgn * WALL_TOP_LIP_W  # ±58 при WALL_TOP_LIP_W=6

    # Профиль треугольника в XZ (ориентация в зависимости от стороны)
    pts = [
        (inner_face,    EAVE_Z),
        (lip_inner_edge, EAVE_Z),
        (inner_face,    EAVE_Z - WALL_TOP_LIP_H),
    ]
    profile = cq.Workplane("XZ").polyline(pts).close()
    # v14 FIX: удлиняем lip на 1 мм в КАЖДУЮ сторону, чтобы он заходил в материал
    # фронтонных стенок и образовывал чистый overlap. Без overlap концы lip'а лежат
    # ровно на гранях фронтонов (тангенциально) — слайсер может их печатать как
    # отдельные полоски, плохо приклеивающиеся к остальной стенке (см. pitfalls.md п.12).
    LIP_GABLE_OVERLAP = 1.0
    lip_length = EXT - 2 * WALL_T + 2 * LIP_GABLE_OVERLAP  # 130 мм
    lip = profile.extrude(lip_length)
    # После extrude: Y от -lip_length до 0. Сдвигаем чтобы центрировать на Y=0.
    lip = lip.translate((0, lip_length / 2, 0))
    return lip


def _make_roof_groove(x_outer: float) -> cq.Workplane:
    """Паз на верхушке боковины (с учётом утолщения lip)."""
    sgn = -1.0 if x_outer < 0 else 1.0
    # Утолщённая стенка идёт от outer_face (±70) до lip_inner_edge (±58) = 12 мм всего.
    # Центр утолщённой стенки на X = (x_outer + lip_inner_edge)/2 = ±64
    # Паз центрируем на этом X.
    inner_face = x_outer - sgn * WALL_T
    lip_inner_edge = inner_face - sgn * WALL_TOP_LIP_W
    groove_center_x = (x_outer + lip_inner_edge) / 2  # = ±64
    groove_len = EXT - 2 * WALL_T - 2 * ROOF_GROOVE_MARGIN  # 122 мм
    groove = cq.Workplane("XY").box(
        ROOF_GROOVE_W, groove_len, ROOF_GROOVE_D + 1
    ).translate((
        groove_center_x,
        0,
        EAVE_Z - ROOF_GROOVE_D / 2 + 0.5  # cutter чуть выше верха стенки, чтобы открыть паз сверху
    ))
    return groove


def _make_entrance_cutter() -> cq.Workplane:
    """Сквозной леток в передней стенке (Y = -EXT/2)."""
    base_z = FLOOR_T + ENT_Z_BASE
    pts = [(x, y + base_z) for (x, y) in entrance_profile()]
    profile = cq.Workplane("XZ").polyline(pts).close()
    # XZ-workplane normal = -Y, поэтому extrude(+) идёт в -Y.
    # Cutter длиной WALL_T+4, range [Y_translate - (WALL_T+4), Y_translate].
    # Хотим cutter Y=[-72, -64] (сквозь стенку Y=-70..-66 + запас).
    cutter = profile.extrude(WALL_T + 4)
    cutter = cutter.translate((0, -EXT / 2 + WALL_T + 1, 0))  # ty = -65
    return cutter


def _make_window_frame_grooves() -> list[cq.Workplane]:
    """Декоративная рамка-канавка вокруг летка — имитация наличников.
    Только subtractive (cut), без overhang при печати стоя."""
    cutters = []
    margin = 7.0          # отступ рамки от летка
    groove_w = 2.5        # ширина канавки
    groove_depth = 1.2    # глубина (вглубь стенки)
    # Внешние габариты рамки
    f_w = ENT_W + 2 * margin
    f_h = ENT_RECT_H + ENT_PEAK_H + 2 * margin  # высота от низа до верхнего пика
    z_base = FLOOR_T + ENT_Z_BASE - margin
    z_top = z_base + f_h
    # Канавки расположим на Y близко к внешней грани (Y = -EXT/2).
    # Cutter — тонкий box, Y span groove_depth*2, центрирован на стенке.
    # Cut уйдёт на groove_depth внутрь стенки.
    y_at = -EXT / 2 + groove_depth  # центр cutter'а: чтобы он торчал на groove_depth внутрь
    # 4 стороны прямоугольника-рамки
    # Низ
    cutters.append(cq.Workplane("XY").box(f_w, groove_depth * 2, groove_w)
                   .translate((0, y_at, z_base)))
    # Верх (горизонтальный, до пика остаётся margin — упростим до прямой линии)
    cutters.append(cq.Workplane("XY").box(f_w, groove_depth * 2, groove_w)
                   .translate((0, y_at, z_top)))
    # Левая вертикальная
    cutters.append(cq.Workplane("XY").box(groove_w, groove_depth * 2, f_h)
                   .translate((-f_w / 2, y_at, z_base + f_h / 2)))
    # Правая вертикальная
    cutters.append(cq.Workplane("XY").box(groove_w, groove_depth * 2, f_h)
                   .translate((f_w / 2, y_at, z_base + f_h / 2)))
    return cutters


def _make_vent_cutters() -> list[cq.Workplane]:
    """Вертикальные щели вентиляции в обеих боковинах, под карнизом."""
    cutters = []
    z_center = FLOOR_T + WALL_H - 14.0  # 14 мм ниже карниза
    spacing = (EXT - 30) / (N_VENT - 1)
    xs = [-(EXT - 30) / 2 + i * spacing for i in range(N_VENT)]
    for sx in (-1, 1):
        for x_off in xs:
            # Stенка на X = ±EXT/2, толщина 4
            slot = cq.Workplane("YZ").rect(VENT_W, VENT_H).extrude(WALL_T + 4) \
                .translate((sx * (EXT / 2) - sx * (WALL_T / 2 + 1), x_off, z_center))
            # Выше: ось Y используется как длина щели; нам нужно по Y
            # Перерисую через box:
            slot = cq.Workplane("XY").box(WALL_T + 4, VENT_W, VENT_H) \
                .translate((sx * (EXT / 2), x_off, z_center))
            cutters.append(slot)
    return cutters


def _make_bottom_text_lines() -> list[cq.Workplane]:
    """Множество параллельных диагональных строк гравировки, покрывающих всё дно.
    Возвращает список cutter'ов (по одному на строку).

    Алгоритм:
      1. Сгенерировать 3D-текст ОДИН раз ("MARK " * BOTTOM_TEXT_REPEAT)
      2. Зеркалим по X (для правильного чтения после переворота)
      3. Скопировать N раз с разным смещением по Y
      4. Каждую копию повернуть на BOTTOM_TEXT_ANGLE вокруг Z
      → получаем N параллельных диагональных строк, заполняющих всю площадь дна.

    Текст cutter'ов длиннее размера дна — выходящие за пределы части
    при `base.cut(line)` ничего не режут (нет материала)."""
    long_text = BOTTOM_TEXT_UNIT * BOTTOM_TEXT_REPEAT

    # Генерируем текст ОДНОГО РАЗА (text() в CadQuery медленный)
    base_solid = (cq.Workplane("XY")
                  .text(long_text, BOTTOM_TEXT_SIZE, BOTTOM_TEXT_DEPTH,
                        font=BOTTOM_TEXT_FONT)
                  .mirror("YZ")
                  .val())  # вытаскиваем Compound из Workplane

    lines = []
    for i in range(BOTTOM_TEXT_N_LINES):
        # Центрируем все строки относительно центра дна
        offset_y = (i - (BOTTOM_TEXT_N_LINES - 1) / 2) * BOTTOM_TEXT_LINE_SPACING
        # Сначала сдвиг по Y (до поворота — это будет перпендикуляр к строкам после поворота)
        translated = base_solid.translate(cq.Vector(0, offset_y, 0))
        line_wp = cq.Workplane("XY").newObject([translated])
        # Поворот всей строки на нужный угол вокруг Z
        line_wp = line_wp.rotate((0, 0, 0), (0, 0, 1), BOTTOM_TEXT_ANGLE)
        lines.append(line_wp)

    return lines


def _make_drain_cutters() -> list[cq.Workplane]:
    """Пирамидальная выемка в полу + центральный сливной канал.

    Пирамида: основание DRAIN_PYRAMID_BASE×DRAIN_PYRAMID_BASE на верху пола (z=FLOOR_T),
    вершина в центре опущена на DRAIN_DEPRESSION (z=FLOOR_T-DRAIN_DEPRESSION).
    Вода с любой точки полости стекает к центру.

    Сливной канал: цилиндр Ø DRAIN_D, проходит сквозь пол от вершины пирамиды до низа базы.
    Печатается БЕЗ поддержек: каждый верхний слой меньше нижнего (нет overhang)."""
    cutters = []

    # Пирамида: loft от точки (тонкий квадрат 0.5×0.5) внизу к большому квадрату вверху
    apex_size = 0.5  # маленький квадрат вместо точки (loft не любит точки)
    pyramid = (cq.Workplane("XY")
               .rect(apex_size, apex_size)
               .workplane(offset=DRAIN_DEPRESSION)
               .rect(DRAIN_PYRAMID_BASE, DRAIN_PYRAMID_BASE)
               .loft(combine=True))
    # Loft создал: apex на z=0, base на z=DRAIN_DEPRESSION
    # Хотим: base на z=FLOOR_T (верх пола), apex на z=FLOOR_T-DRAIN_DEPRESSION
    pyramid = pyramid.translate((0, 0, FLOOR_T - DRAIN_DEPRESSION))
    cutters.append(pyramid)

    # Центральный слив (вертикальный цилиндр) — через ВСЁ дно от вершины пирамиды до нижней грани
    drain = cq.Workplane("XY").cylinder(FLOOR_T + 2, DRAIN_D / 2) \
        .translate((0, 0, FLOOR_T / 2))
    cutters.append(drain)

    # v14: 4 боковых дренажа в кардинальных точках — резерв если центр засорится
    # Расположены на полпути от центра к стенкам (Y=±55, X=0 и X=±55, Y=0)
    side_positions = [
        (SIDE_DRAIN_OFFSET, 0),
        (-SIDE_DRAIN_OFFSET, 0),
        (0, SIDE_DRAIN_OFFSET),
        (0, -SIDE_DRAIN_OFFSET),
    ]
    for sx, sy in side_positions:
        side_drain = cq.Workplane("XY").cylinder(FLOOR_T + 2, SIDE_DRAIN_D / 2) \
            .translate((sx, sy, FLOOR_T / 2))
        cutters.append(side_drain)

    return cutters


def _make_keyhole_cutters() -> list[cq.Workplane]:
    """3 keyhole-слота в задней стенке (Y = +EXT/2): треугольник из 2 сверху + 1 снизу.

    ОРИЕНТАЦИЯ ВАЖНА: большой круг СНИЗУ, слот ВВЕРХ от него.
    Логика гравитационного крепления:
      1. Совмещаешь большой круг с штырём → шляпка штыря проходит через круг
      2. Отпускаешь скворечник → он опускается под действием силы тяжести
      3. Штырь относительно скворечника поднимается ВВЕРХ → попадает в слот
      4. Шляпка штыря (Ø8 > щели Ø4.5) застревает в слоте → скворечник висит
    Если ориентировать наоборот (слот вниз), скворечник упадёт — шляпка
    выскользнет через большой круг."""
    cutters = []
    # 3 точки крепления: (X, Z_от_пола) — kh_z указывает на нижний край БОЛЬШОГО КРУГА
    keyholes = [
        (-KH_X_TOP, KH_Z_TOP),  # верх-слева
        (+KH_X_TOP, KH_Z_TOP),  # верх-справа
        (0,         KH_Z_BOT),  # низ-центр
    ]
    for x_offset, kh_z in keyholes:
        # Большой круг: нижний край на Z = FLOOR_T + kh_z, центр на FLOOR_T + kh_z + KH_BIG_D/2
        bigcircle_z_center = FLOOR_T + kh_z + KH_BIG_D / 2
        big = cq.Workplane("XZ").circle(KH_BIG_D / 2).extrude(WALL_T + 4) \
            .translate((x_offset, EXT / 2 + 2, bigcircle_z_center))
        # Слот: нижний край ВНУТРИ большого круга (overlap 2 мм), простирается вверх.
        # Overlap нужен чтобы boolean-объединение было манифольдным
        # (если просто соприкасаются по ребру, получается non-watertight геометрия).
        slot_overlap = 2.0
        slot_z_bottom = bigcircle_z_center + KH_BIG_D / 2 - slot_overlap
        slot_actual_len = KH_SLOT_LEN + slot_overlap  # компенсируем, чтобы верх слота не сместился
        slot_z_center = slot_z_bottom + slot_actual_len / 2
        slot = cq.Workplane("XZ").rect(KH_SLOT_W, slot_actual_len).extrude(WALL_T + 4) \
            .translate((x_offset, EXT / 2 + 2, slot_z_center))
        cutters.append(big)
        cutters.append(slot)
    return cutters


def _make_deco_grooves() -> list[cq.Workplane]:
    """Декоративные горизонтальные канавки по периметру стенок (имитация фахверка)."""
    cutters = []
    for z_off in DECO_STRIP_Z:
        z = FLOOR_T + z_off
        # Срезаем ободок снаружи: делаем «пояс» вокруг
        # Для простоты — 4 длинных бруска по периметру
        # Передняя/задняя
        for sy in (-1, 1):
            cut = cq.Workplane("XY").box(EXT + 2, DECO_STRIP_D * 2, DECO_STRIP_H) \
                .translate((0, sy * (EXT / 2 + DECO_STRIP_D - DECO_STRIP_D), z))
            # Перерисую корректно: пояс вокруг, чуть утопленный
            cut = cq.Workplane("XY").box(EXT + 0.2, DECO_STRIP_D * 2, DECO_STRIP_H) \
                .translate((0, sy * EXT / 2, z))
            cutters.append(cut)
        # Боковые
        for sx in (-1, 1):
            cut = cq.Workplane("XY").box(DECO_STRIP_D * 2, EXT + 0.2, DECO_STRIP_H) \
                .translate((sx * EXT / 2, 0, z))
            cutters.append(cut)
    return cutters


def _make_tie_holes() -> list[cq.Workplane]:
    """Сквозные отверстия в пиках фронтонов (Y-направление) для стяжки крыши
    проволокой/верёвкой/стяжкой. Расположены на 10 мм ниже самого пика —
    в этой точке стенка фронтона имеет ширину ~25 мм, отверстие 4 мм безопасно."""
    cutters = []
    z_hole = GABLE_PEAK_Z - 10  # 10 мм ниже пика, где фронтон ~25 мм шириной
    # Передний фронтон: Y от -70 до -66
    front = cq.Workplane("XZ").circle(2.0).extrude(WALL_T + 4) \
        .translate((0, -EXT / 2 + WALL_T + 1, z_hole))
    # Задний фронтон: Y от +66 до +70
    back = cq.Workplane("XZ").circle(2.0).extrude(WALL_T + 4) \
        .translate((0, EXT / 2 + 2, z_hole))
    return [front, back]


# ============================================================
# 2. КРЫША — один скат (печатать 2 копии)
# ============================================================
def make_roof_half() -> cq.Workplane:
    """Скат печатается плашмя: внутренняя поверхность ВВЕРХ
    (фиксирующие выемки и якорные пазы видны сверху, снаружи — черепица).

    v18 геометрия:
      • Панель: box(length × width × ROOF_T) — изначально прямоугольный скат
      • Ребро (rib) на верхней (после флипа — внутренней) грани
      • МИТР на коньковой кромке: тонкий клин ROOF_T*tan(a) × ROOF_T в сечении,
        длиной во весь скат. После наклона при сборке кромка становится
        ВЕРТИКАЛЬНОЙ в мировой системе → два ската встречаются грань-в-грань
        вдоль линии конька без щели и без перекрытия.
    """

    length = ROOF_PANEL_Y
    width = ROOF_SLOPE_LEN
    sin_a = math.sin(ROOF_ANGLE)
    cos_a = math.cos(ROOF_ANGLE)

    # 1. База ската
    panel = cq.Workplane("XY").box(length, width, ROOF_T) \
        .translate((0, 0, ROOF_T / 2))

    # 2. ШИП на нижней (внутренней) стороне — главный замок крыши.
    # При сборке шип опускается в паз на верхушке боковой стенки базы.
    #
    # Координаты при сборке: панель → flip-X-180 → rotateZ-90 → tiltY-(-a) →
    # перенос так, чтобы НАРУЖНЫЙ коньковой угол лёг на X=0 (см. make_assembly).
    # Сводный transform для точки (x_local, y_local, z_local) панели:
    #   world_X = y_local*cos(a) + z_local*sin(a) - width/2 * cos(a)
    # Для центра ребра (y=rib_panel_y, z=ROOF_T+ROOF_RIB_H/2) хотим world_X = -groove_center
    # (для левого ската; правый = mirror). Решаем относительно rib_panel_y:
    groove_center_x = (EXT - WALL_T - WALL_TOP_LIP_W) / 2  # = 64 при текущих параметрах
    rib_z_center_local = ROOF_T + ROOF_RIB_H / 2
    rib_panel_y = width / 2 - (groove_center_x + rib_z_center_local * sin_a) / cos_a
    # Длина шипа: на ROOF_RIB_LEN_MARGIN короче паза с каждой стороны
    groove_length = EXT - 2 * WALL_T - 2 * ROOF_GROOVE_MARGIN
    rib_length = groove_length - 2 * ROOF_RIB_LEN_MARGIN
    rib = cq.Workplane("XY").box(rib_length, ROOF_RIB_W, ROOF_RIB_H) \
        .translate((0, rib_panel_y, ROOF_T + ROOF_RIB_H / 2))
    panel = panel.union(rib)

    # 3. Резервные отверстия для проволочной стяжки (на случай сильного ветра)
    # 2 маленьких отверстия Ø3 мм, ближе к коньковому краю
    tie_offset_x = EXT / 2 - WALL_T / 2  # над фронтонами
    tie_offset_y = width / 2 - 14
    for sx in (-1, 1):
        hole = cq.Workplane("XY").cylinder(ROOF_T + ROOF_RIB_H + 4, ROOF_TIE_HOLE_D / 2) \
            .translate((sx * tie_offset_x, tie_offset_y, ROOF_T / 2))
        panel = panel.cut(hole)

    # 4. МИТРОВАЯ ПОДРЕЗКА кромки конька (главный фикс v18 — закрытие щели).
    #
    # При наклоне на ROOF_ANGLE прямоугольная коньковая кромка превращается в
    # «лестницу»: НАРУЖНЫЙ угол скрывается на ROOF_T*sin(a) ниже внутреннего по X
    # и на ROOF_T*cos(a) ниже по Z. Два таких ската встречаются ВНУТРЕННИМИ
    # углами, а наружные расходятся → треугольная щель сверху.
    #
    # Подрезка: снимаем клин с +Y (коньковой) стороны панели так, чтобы плоскость
    # реза в мировой системе стала вертикальной (X=const). Плоскость реза в
    # panel-local: cos(a)*Y + sin(a)*Z = cos(a)*width/2.
    # В Y-Z сечении клин — треугольник с вершинами:
    #   A = (+width/2, 0)         наружный коньковой угол (на плоскости реза)
    #   B = (+width/2, ROOF_T)    внутренний коньковой угол (удаляется)
    #   C = (+width/2 - inset, ROOF_T)  где плоскость реза пересекает внутр. грань
    # inset = ROOF_T * tan(a). Клин вытянут вдоль X (длина ската).
    miter_inset = ROOF_T * math.tan(ROOF_ANGLE)
    ext = 5.0  # припуск, чтобы cutter уверенно вышел за пределы панели
    miter_pts = [
        (width / 2 - miter_inset, ROOF_T),
        (width / 2 + ext, ROOF_T),
        (width / 2 + ext, -ext),
        (width / 2, -ext),
        (width / 2, 0),
    ]
    # YZ-workplane (нормаль +X), extrude → +X. Сдвигаем, чтобы cutter покрыл
    # всю длину панели с обеих сторон.
    miter_cutter = (cq.Workplane("YZ")
                    .polyline(miter_pts).close()
                    .extrude(length + 2 * ext)
                    .translate((-length / 2 - ext, 0, 0)))
    panel = panel.cut(miter_cutter)

    return panel


# ============================================================
# 3. КЛАЙМБ-ТЕКСТУРА на внутренней грани передней стенки
#    Горизонтальные канавки чтобы птенцы могли цепляться когтями
#    при подъёме к летку — на гладком пластике они скользят.
# ============================================================
def _make_climb_grooves() -> list[cq.Workplane]:
    """Горизонтальные канавки на внутренней грани передней стенки (Y = -EXT/2 + WALL_T).
    Каждая канавка — тонкий горизонтальный паз 0.7 мм глубиной, расположен ниже летка."""
    cutters = []
    inner_face_y = -EXT / 2 + WALL_T          # внутренняя грань передней стенки = -64
    # Cutter для каждой канавки: тонкий box, разрезает стенку с внутренней стороны
    # Y span: от inner_face_y - depth (внутри стенки) до inner_face_y + 1 (overlap с полостью)
    # — overlap нужен для манифольдности boolean cut'а (см. pitfalls.md п.12)
    cutter_y_thickness = CLIMB_GROOVE_DEPTH + 1.0
    cutter_y_center = inner_face_y - CLIMB_GROOVE_DEPTH / 2 + 0.5

    cavity_w = EXT - 2 * WALL_T               # внутренняя ширина полости
    cutter_x_width = cavity_w - 4.0           # 2 мм отступ от боковых стенок

    z_top = ENT_Z_BASE - CLIMB_Z_BELOW_ENT    # верх климб-зоны (5 мм ниже летка)
    n_grooves = int((z_top - CLIMB_Z_START) / CLIMB_GROOVE_SPACING) + 1

    for i in range(n_grooves):
        z_local = CLIMB_Z_START + i * CLIMB_GROOVE_SPACING
        z_world = FLOOR_T + z_local
        cutter = cq.Workplane("XY").box(cutter_x_width, cutter_y_thickness, CLIMB_GROOVE_H) \
            .translate((0, cutter_y_center, z_world))
        cutters.append(cutter)
    return cutters


# ============================================================
# 4. МОНТАЖНАЯ ПЛАТА (Tree Mount Plate)
#    Прикручивается к дереву/стене 4 саморезами; скворечник вешается на 2 штыря
#    через keyhole-слоты в задней стенке. Печатается плашмя (тыльной стороной на стол),
#    штыри торчат вверх — печатаются как короткие цилиндры, без поддержек.
# ============================================================
def make_tree_mount() -> cq.Workplane:
    # 1. Основа платы
    plate = cq.Workplane("XY").box(TMP_W, TMP_H, TMP_T) \
        .translate((0, 0, TMP_T / 2))

    # 2. 4 отверстия под саморезы с зенковкой под шляпку
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * TMP_SCREW_DX, sy * TMP_SCREW_DY
            # Сквозное отверстие
            through = cq.Workplane("XY").cylinder(TMP_T + 2, TMP_SCREW_D / 2) \
                .translate((x, y, TMP_T / 2))
            # Зенковка с лицевой стороны (Z = TMP_T side)
            cbore = cq.Workplane("XY").cylinder(TMP_SCREW_HEAD_DEPTH + 0.5, TMP_SCREW_HEAD_D / 2) \
                .translate((x, y, TMP_T - TMP_SCREW_HEAD_DEPTH / 2 + 0.25))
            plate = plate.cut(through).cut(cbore)

    # 3. 3 грибовидных штыря — треугольник: 2 сверху + 1 снизу
    pin_positions = [
        (-TMP_PIN_X_TOP, TMP_PIN_Y_TOP),   # верх-слева
        (+TMP_PIN_X_TOP, TMP_PIN_Y_TOP),   # верх-справа
        (0,              TMP_PIN_Y_BOT),   # низ-центр
    ]
    for px, py in pin_positions:
        plate = plate.union(_make_mushroom_pin(at_x=px, at_y=py))

    return plate


def _make_mushroom_pin(at_x: float, at_y: float) -> cq.Workplane:
    """Грибовидный штырь: стебель + 45° чамфер + шляпка.
    Сборка из примитивов: cylinder (стебель) + cone (чамфер) + cylinder (шляпка).
    Все в осях с Z вверх; основание на лицевой поверхности платы (Z = TMP_T)."""
    chamfer_h = (TMP_PIN_HEAD_D - TMP_PIN_STEM_D) / 2  # 45° → высота = радиальное расширение

    # Стебель (от Z = TMP_T до Z = TMP_T + STEM_H)
    stem = cq.Workplane("XY").cylinder(TMP_PIN_STEM_H, TMP_PIN_STEM_D / 2) \
        .translate((at_x, at_y, TMP_T + TMP_PIN_STEM_H / 2))

    # Чамфер (конус, от Z = TMP_T+STEM_H до Z = TMP_T+STEM_H+chamfer_h)
    cone_solid = cq.Solid.makeCone(
        TMP_PIN_STEM_D / 2, TMP_PIN_HEAD_D / 2, chamfer_h
    )
    cone = cq.Workplane("XY").newObject([cone_solid]) \
        .translate((at_x, at_y, TMP_T + TMP_PIN_STEM_H))

    # Шляпка
    z_head = TMP_T + TMP_PIN_STEM_H + chamfer_h + TMP_PIN_HEAD_H / 2
    head = cq.Workplane("XY").cylinder(TMP_PIN_HEAD_H, TMP_PIN_HEAD_D / 2) \
        .translate((at_x, at_y, z_head))

    return stem.union(cone).union(head)


# ============================================================
# СБОРКА (визуализация)
# ============================================================
def make_assembly() -> cq.Workplane:
    """Возвращает Compound всех деталей в положении сборки (для preview).

    Сборка скатов (v18):
      В panel-local оси: X = длина (вдоль конька), Y = ширина (вдоль ската),
      Z = толщина. Inner-face (с ребром) на Z=ROOF_T.

      Преобразования ЛЕВОГО ската:
        1) flip-X-180   → inner-face смотрит вниз, ребро торчит -Z
        2) rotateZ-90   → длина теперь вдоль Y (как нужно в сборке)
        3) tiltY-(-a)   → скат наклонён, +X сторона панели стала верхом
        4) translate    → НАРУЖНАЯ коньковая кромка ставится на (X=0, Z=GABLE_PEAK_Z)

      После шагов 1-3 точка panel-local (x, y, z) → world
        ( y*cos(a) + z*sin(a),  x,  y*sin(a) - z*cos(a) )

      Наружный коньковой угол panel-local (any, +width/2, 0):
        world = (+width/2 * cos(a), x, +width/2 * sin(a))
      Митровая подрезка кромки (см. make_roof_half) гарантирует, что после
      шагов 1-3 МАКСИМАЛЬНЫЙ X панели = +width/2 * cos(a) (не выходит дальше
      внутренней кромкой), поэтому translate переводит наружный угол точно
      на X=0 и обе грани (наружная и внутренняя) кромки лежат на одной
      вертикали в мировой системе.

      Правый скат: зеркало левого через mirror("YZ"), без отдельного расчёта
      поворотов — это исключает ошибку с противоположным знаком угла Y
      (раньше правое ребро уходило на X≈+81 вместо паза +65).
    """
    base = make_base()
    mount = make_tree_mount()

    sin_a = math.sin(ROOF_ANGLE)
    cos_a = math.cos(ROOF_ANGLE)
    outer_ridge_x = (ROOF_SLOPE_LEN / 2) * cos_a   # = 46.05 при текущих параметрах
    outer_ridge_z = (ROOF_SLOPE_LEN / 2) * sin_a   # = 29.53

    roof_l = make_roof_half() \
        .rotate((0, 0, 0), (1, 0, 0), 180) \
        .rotate((0, 0, 0), (0, 0, 1), 90) \
        .rotate((0, 0, 0), (0, 1, 0), -math.degrees(ROOF_ANGLE)) \
        .translate((-outer_ridge_x, 0, GABLE_PEAK_Z - outer_ridge_z))

    roof_r = roof_l.mirror("YZ")

    # Монтажная плата сзади скворечника. Поворот вокруг X на 90° → плата
    # стоит вертикально; лицо со штырями смотрит в -Y, прижимаясь к задней стенке.
    mount_assembled = mount.rotate((0, 0, 0), (1, 0, 0), 90)
    kh_mid_z = FLOOR_T + (KH_Z_TOP + KH_Z_BOT) / 2 + KH_BIG_D / 2
    mount_assembled = mount_assembled.translate((0, EXT / 2 + 12, kh_mid_z))

    return base.union(roof_l).union(roof_r).union(mount_assembled)


# ============================================================
# ВАЛИДАЦИЯ + ЭКСПОРТ
# ============================================================
def validate(name: str, wp: cq.Workplane, bed=(220, 220, 250)):
    bb = wp.val().BoundingBox()
    dims = (bb.xlen, bb.ylen, bb.zlen)
    fits = all(d <= b for d, b in zip(dims, bed))
    print(f"  {name:14s}  bbox = {dims[0]:7.2f} x {dims[1]:7.2f} x {dims[2]:6.2f} mm   "
          f"{'[OK]' if fits else '[!! NOT FITTING !!]'}")
    return fits


def main():
    out = Path.home() / "Downloads" / f"birdhouse_v{VERSION}"
    out.mkdir(parents=True, exist_ok=True)
    prefix = f"birdhouse_v{VERSION}"

    print(f"Building birdhouse v{VERSION}...")
    parts = {
        "base":       make_base(),
        "roof_half":  make_roof_half(),
        "tree_mount": make_tree_mount(),
    }

    print("\nValidation (Creality K1C: 220×220×250 mm):")
    for name, wp in parts.items():
        validate(name, wp)

    print("\nExporting STLs...")
    for name, wp in parts.items():
        path = out / f"{prefix}_{name}.stl"
        cq.exporters.export(wp, str(path), tolerance=0.05, angularTolerance=0.1)
        print(f"  -> {path.name}")

    print("\nBuilding assembly preview...")
    asm = make_assembly()
    asm_path = out / f"{prefix}_assembly.stl"
    cq.exporters.export(asm, str(asm_path), tolerance=0.05, angularTolerance=0.1)
    print(f"  -> {asm_path.name}")
    print(f"\nDone. Files: {out}")


if __name__ == "__main__":
    main()
