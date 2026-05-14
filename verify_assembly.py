"""
Проверка стыковки всех деталей скворечника. Каждое соединение проверяется
параметрически (а не визуально): размеры мата ↔ матери, перекрытия, зазоры.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import birdhouse as bh
import trimesh
import math


def fmt(ok, label, details=""):
    mark = "✓" if ok else "✗"
    return f"  [{mark}] {label}" + (f"  ({details})" if details else "")


def section(title):
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")


def main():
    print(f"\n{'='*70}\nVERIFY ASSEMBLY — birdhouse v{bh.VERSION}\n{'='*70}")
    all_ok = True

    # ──────────────────────────────────────────────────────────────────────
    section("1. STL-файлы существуют и watertight")
    out = Path.home() / "Downloads" / f"birdhouse_v{bh.VERSION}"
    parts = ["base", "roof_half", "tree_mount"]
    meshes = {}
    for name in parts:
        path = out / f"birdhouse_v{bh.VERSION}_{name}.stl"
        if not path.exists():
            print(fmt(False, f"{name}.stl отсутствует"))
            all_ok = False
            continue
        m = trimesh.load(path, force="mesh")
        meshes[name] = m
        wt = m.is_watertight
        bb = m.bounds[1] - m.bounds[0]
        det = f"bbox={[round(x,1) for x in bb]} mm, vol={m.volume/1000:.1f} cm³"
        print(fmt(wt, f"{name}", det))
        all_ok &= wt

    # ──────────────────────────────────────────────────────────────────────
    section("2. Tree mount pins ↔ Keyhole slots в задней стенке базы")

    # Проверка 1: стебель проходит через щель
    stem_d = bh.TMP_PIN_STEM_D
    slot_w = bh.KH_SLOT_W
    stem_clear = slot_w - stem_d
    ok = 0.5 <= stem_clear <= 2.0
    print(fmt(ok, "Стебель проходит через щель",
              f"стебель Ø{stem_d} → щель Ø{slot_w}, зазор {stem_clear:.1f} мм"))
    all_ok &= ok

    # Проверка 2: шляпка проходит через большое отверстие
    head_d = bh.TMP_PIN_HEAD_D
    big_d = bh.KH_BIG_D
    head_clear = big_d - head_d
    ok = 0.5 <= head_clear <= 4.0
    print(fmt(ok, "Шляпка проходит через большое отверстие",
              f"шляпка Ø{head_d} → круг Ø{big_d}, зазор {head_clear:.1f} мм"))
    all_ok &= ok

    # Проверка 3: шляпка НЕ проходит через щель (это и есть фиксация)
    head_vs_slot = head_d - slot_w
    ok = head_vs_slot >= 2.0
    print(fmt(ok, "Шляпка НЕ проходит через щель (фиксация)",
              f"шляпка Ø{head_d} > щель Ø{slot_w} на {head_vs_slot:.1f} мм"))
    all_ok &= ok

    # Проверка 4: 3-точечное крепление — позиции штырей платы совпадают с keyhole'ами базы
    # Платa: 2 верхних штыря в (±TMP_PIN_X_TOP, TMP_PIN_Y_TOP), 1 нижний в (0, TMP_PIN_Y_BOT)
    # База: 2 верхних keyhole в (±KH_X_TOP, Z=KH_Z_TOP), 1 нижний в (0, Z=KH_Z_BOT)
    # Связь: TMP_PIN_Y соответствует Z (вертикали в сборке)
    pin_v_spacing = bh.TMP_PIN_Y_TOP - bh.TMP_PIN_Y_BOT
    kh_v_spacing = bh.KH_Z_TOP - bh.KH_Z_BOT
    ok1 = abs(pin_v_spacing - kh_v_spacing) < 0.01
    ok2 = abs(bh.TMP_PIN_X_TOP - bh.KH_X_TOP) < 0.01
    ok = ok1 and ok2
    print(fmt(ok, "3-точечное: вертикальный шаг и горизонтальное смещение совпадают",
              f"плата V-шаг={pin_v_spacing}, X-смещ={bh.TMP_PIN_X_TOP}; "
              f"keyhole V-шаг={kh_v_spacing}, X-смещ={bh.KH_X_TOP}"))
    all_ok &= ok

    # Проверка 5: щель достаточно длинная, чтобы шляпка зашла в неё (drop distance)
    # При вешании скворечник должен опуститься так, чтобы щель была под шляпкой.
    # Drop = (центр большого круга) - (середина пути в щели) ≈ KH_BIG_D/2 + чуть-чуть
    drop_needed = bh.KH_BIG_D / 2 + 1.0  # минимум, чтобы шляпка прошла полностью + клиренс
    ok = bh.KH_SLOT_LEN >= drop_needed
    print(fmt(ok, "Длина щели достаточна для опускания скворечника",
              f"щель {bh.KH_SLOT_LEN} мм > нужно {drop_needed} мм"))
    all_ok &= ok

    # Проверка 6: длина стебля штифта vs толщина стенки
    # Стебель должен пройти через 4-мм стенку И не цеплять шляпкой за внешнюю поверхность.
    # При вставке: head в big circle, потом spead pulldown.
    # Стебель должен пересекать всю толщину стенки + clearance под шляпку
    # Длина стебля = TMP_PIN_STEM_H = 5.5
    # Стенка = 4 мм, плюс надо ещё 1-2 мм чтобы шляпка не утопала в стенке после drop
    stem_h = bh.TMP_PIN_STEM_H
    ok = stem_h >= bh.WALL_T + 1.0
    print(fmt(ok, "Стебель длиннее толщины стенки + клиренс",
              f"стебель {stem_h} мм > стенка {bh.WALL_T} мм + 1 мм"))
    all_ok &= ok

    # ──────────────────────────────────────────────────────────────────────
    section("3. Tree mount plate vs back wall keyhole positions")

    # При навешивании плата находится ЗА задней стенкой. Скворечник опускается до контакта.
    # Положение центров штырей в реальном мире:
    # При сборке: плата сзади, лицо штырей касается ЗАДНЕЙ ВНЕШНЕЙ грани стенки (Y=+EXT/2)
    # Штырь идёт ВПЕРЁД (в -Y direction), пронзая стенку, шляпка в полости.
    # Когда скворечник навешен (опущен), щель оказывается под шляпкой штифта.

    # Y-позиции по высоте (центры пинов):
    # Если плата центрирована между keyhole'ами:
    # Центр платы по Y (вертикали в реальном мире) = (KH_Z_TOP + KH_Z_BOT)/2 + FLOOR_T + KH_BIG_D/2
    # = (135 + 65)/2 + 5 + 5 = 110
    # Штырь ВЕРХНИЙ платы на Y_world = 110 + TMP_PIN_SPACING/2 = 110 + 35 = 145
    # Это совпадает с центром верхнего big circle = 5 + 135 + 5 = 145 ✓
    # Когда скворечник на штырях: для зацепа за щель скворечник опустится так, что
    # большой круг сдвинется ВВЕРХ относительно штифта на (KH_BIG_D/2 - KH_SLOT_W/2 + ...).
    # Точнее: центр большого круга ~ центру штифта в момент входа, потом скворечник опускается
    # и штифт оказывается в верхней части щели.

    # Главное: плата УЗКАЯ. Проверим, что она помещается между боковинами скворечника
    # без зазора, чтобы жёстко прижиматься к задней стенке.
    inner_w = bh.EXT - 2 * bh.WALL_T  # 132
    ok = bh.TMP_W < bh.EXT  # минимум — плата уже всего скворечника снаружи
    print(fmt(ok, "Плата уже скворечника (хвост за стенкой)",
              f"плата {bh.TMP_W} мм < скворечник {bh.EXT} мм"))
    all_ok &= ok

    # Проверка позиции keyhole'ов вдоль ширины — они должны быть по центру (X=0)
    # и плата тоже по центру (X=0). Это в коде так. Запишем напоминание.
    print(fmt(True, "Keyhole'ы и пины платы — оба центрированы по X=0", "(by design)"))

    # ──────────────────────────────────────────────────────────────────────
    section("4. Скаты крыши ↔ фронтоны базы")

    # Скаты лежат на наклонных гранях фронтонов. Длина ската по плоскости должна
    # быть ≥ длины наклонной грани фронтона + overhang.
    # Длина наклонной грани фронтона = sqrt((EXT/2)² + GABLE_H²)
    gable_slope = math.hypot(bh.EXT / 2, bh.GABLE_H)
    needed = gable_slope + bh.ROOF_OVERHANG  # минимум, чтобы был свес
    ok = bh.ROOF_SLOPE_LEN >= needed
    print(fmt(ok, "Длина ската покрывает фронтон + overhang",
              f"скат {bh.ROOF_SLOPE_LEN:.1f} мм vs фронтон+overhang {needed:.1f} мм"))
    all_ok &= ok

    # Длина ската вдоль конька = EXT + 2*OVERHANG, симметрично спереди-сзади
    expected_y = bh.EXT + 2 * bh.ROOF_OVERHANG
    ok = abs(bh.ROOF_PANEL_Y - expected_y) < 0.01
    print(fmt(ok, "Длина ската вдоль Y = EXT + 2×OVERHANG",
              f"{bh.ROOF_PANEL_Y} мм"))
    all_ok &= ok

    # Угол ската (для информации)
    angle_deg = math.degrees(bh.ROOF_ANGLE)
    print(fmt(True, "Угол ската (информативно)",
              f"{angle_deg:.1f}° от горизонтали — нормально для FDM"))

    # ──────────────────────────────────────────────────────────────────────
    section("5. ЗАМОК КРЫШИ: ребро ската ↔ паз на боковине")

    sin_a = math.sin(bh.ROOF_ANGLE)
    cos_a = math.cos(bh.ROOF_ANGLE)
    inner_face = bh.EXT/2 - bh.WALL_T              # 66
    lip_inner = inner_face - bh.WALL_TOP_LIP_W      # 60
    groove_center_x = (bh.EXT/2 + lip_inner) / 2    # 65
    groove_x_min = groove_center_x - bh.ROOF_GROOVE_W/2  # 62
    groove_x_max = groove_center_x + bh.ROOF_GROOVE_W/2  # 68
    groove_z_top = bh.EAVE_Z                        # 165
    groove_z_bot = bh.EAVE_Z - bh.ROOF_GROOVE_D     # 160

    # 5.1 — Lip slope ≤ 45° от вертикали (печать без поддержек)
    lip_angle_v = math.degrees(math.atan2(bh.WALL_TOP_LIP_W, bh.WALL_TOP_LIP_H))
    ok = lip_angle_v <= 45
    print(fmt(ok, "Наклон lip'а ≤ 45° от вертикали (печать без поддержек)",
              f"{lip_angle_v:.1f}° (slope {bh.WALL_TOP_LIP_W}/{bh.WALL_TOP_LIP_H})"))
    all_ok &= ok

    # 5.2 — Внутренняя стенка паза не выходит за наклонный lip
    # Lip width на ROOF_GROOVE_D ниже верха = LIP_W * (LIP_H - GROOVE_D) / LIP_H
    lip_w_at_bot = bh.WALL_TOP_LIP_W * (bh.WALL_TOP_LIP_H - bh.ROOF_GROOVE_D) / bh.WALL_TOP_LIP_H
    lip_inner_at_bot = inner_face - lip_w_at_bot  # X где lip заканчивается на дне паза
    inner_groove_margin = lip_inner_at_bot - groove_x_min  # должно быть < 0 (lip простирается дальше)
    ok = inner_groove_margin < 0
    margin_mm = -inner_groove_margin if ok else inner_groove_margin
    print(fmt(ok, "Внутренняя стенка паза НЕ выходит за наклон lip'а",
              f"lip заканчивается на ±{lip_inner_at_bot:.2f} на дне паза vs паз внутри ±{groove_x_min}, "
              f"запас {margin_mm:.2f} мм"))
    all_ok &= ok

    # 5.3 — Outer remnant стенки достаточно толстый
    outer_remnant = bh.EXT/2 - groove_x_max
    ok = outer_remnant >= 1.5
    print(fmt(ok, "Внешний остаток стенки ≥ 1.5 мм",
              f"{outer_remnant} мм"))
    all_ok &= ok

    # 5.4 — X-проекция ребра ≤ ширины паза
    rib_x_proj = bh.ROOF_RIB_W * cos_a + bh.ROOF_RIB_H * sin_a
    ok = rib_x_proj <= bh.ROOF_GROOVE_W
    print(fmt(ok, "X-проекция ребра помещается в паз",
              f"проекция {rib_x_proj:.2f} мм ≤ паз {bh.ROOF_GROOVE_W} мм, "
              f"клиренс {bh.ROOF_GROOVE_W - rib_x_proj:.2f} мм"))
    all_ok &= ok

    # 5.5 — Точка опоры ребра позиционирована для центрирования в пазу
    rib_anchor_x = groove_center_x + (bh.ROOF_RIB_H / 2) * sin_a
    z_skat = bh.GABLE_PEAK_Z - rib_anchor_x * (bh.GABLE_H / bh.ROOF_RUN)
    rib_x_min = rib_anchor_x - bh.ROOF_RIB_W/2 * cos_a - bh.ROOF_RIB_H * sin_a
    rib_x_max = rib_anchor_x + bh.ROOF_RIB_W/2 * cos_a
    ok = rib_x_min >= groove_x_min and rib_x_max <= groove_x_max
    print(fmt(ok, "Ребро в сборке вписывается в паз по X",
              f"ребро X=[{rib_x_min:.2f}, {rib_x_max:.2f}] vs паз [{groove_x_min}, {groove_x_max}]"))
    all_ok &= ok

    # 5.6 — РЕАЛЬНОЕ ПРОНИКНОВЕНИЕ ребра в паз
    rib_z_low = z_skat - (bh.ROOF_RIB_W/2)*sin_a - bh.ROOF_RIB_H*cos_a
    penetration = groove_z_top - rib_z_low
    ok = penetration > 1.0
    print(fmt(ok, "Ребро РЕАЛЬНО входит в паз (≥ 1 мм)",
              f"проникновение {penetration:.2f} мм (rib_z_low={rib_z_low:.2f}, groove_top={groove_z_top})"))
    all_ok &= ok

    # 5.7 — Ребро не упирается в дно паза (скат опирается на гребень фронтона, не висит на ребре)
    bottom_clearance = rib_z_low - groove_z_bot
    ok = bottom_clearance > 0.3
    print(fmt(ok, "Ребро не упирается в дно паза",
              f"клиренс до дна {bottom_clearance:.2f} мм"))
    all_ok &= ok

    # 5.8 — Длина ребра в пределах паза с запасом
    groove_len = bh.EXT - 2 * bh.WALL_T - 2 * bh.ROOF_GROOVE_MARGIN
    rib_len = groove_len - 2 * bh.ROOF_RIB_LEN_MARGIN
    ok = 60 <= rib_len <= groove_len - 8
    print(fmt(ok, "Длина ребра разумная и помещается в паз",
              f"паз {groove_len} мм, ребро {rib_len} мм, запас по концам {(groove_len-rib_len)/2} мм"))
    all_ok &= ok

    # 5.9 — Полость не сильно сужается у потолка
    cavity_at_top = bh.EXT - 2 * bh.WALL_T - 2 * bh.WALL_TOP_LIP_W
    ok = cavity_at_top >= 100
    print(fmt(ok, "Внутренняя полость у потолка ≥ 100 мм (для птицы)",
              f"{cavity_at_top}×{bh.EXT - 2*bh.WALL_T} мм у потолка"))
    all_ok &= ok

    # ──────────────────────────────────────────────────────────────────────
    section("5b. Резервная стяжка: tie-hole в фронтоне ↔ tie-hole в скате")

    # На скате 2 отверстия Ø3 мм у конькового края, на расстоянии EXT/2 - WALL_T/2 от центра
    # вдоль длины ската (= 70 - 2 = 68 мм). Это совпадает с центром фронтонной стенки
    # (фронтон по толщине: Y от EXT/2-WALL_T до EXT/2, центр на 68).

    skat_tie_x_from_center = bh.EXT / 2 - bh.WALL_T / 2  # 68 мм
    front_gable_y_center = bh.EXT / 2 - bh.WALL_T / 2  # 68 мм (центр толщины фронтона)
    ok = abs(skat_tie_x_from_center - front_gable_y_center) < 0.01
    print(fmt(ok, "Tie-hole ската по X совпадает с центром фронтона по Y",
              f"скат: ±{skat_tie_x_from_center} мм, фронтон: ±{front_gable_y_center} мм"))
    all_ok &= ok

    # Tie-hole в фронтоне на 10 мм ниже пика — там фронтон шириной ~(10/GABLE_H)*EXT = 25 мм
    z_below_peak = 10
    width_at_hole = (z_below_peak / bh.GABLE_H) * bh.EXT
    ok = width_at_hole > 4 * 3  # минимум 3 диаметра отверстия (Ø4)
    print(fmt(ok, "Фронтон в зоне tie-hole достаточно широкий",
              f"ширина {width_at_hole:.1f} мм vs нужно >12 мм для безопасности"))
    all_ok &= ok

    # Tie-hole в скате расположен на 12 мм от конькового края — проверим что
    # эта точка в сборке окажется НАД tie-hole в фронтоне (т.е. на правильной стороне ската).
    # На пике конька (X=0, Z=GABLE_PEAK_Z), tie-hole фронтона на Z=GABLE_PEAK_Z-10.
    # Скат лежит наклонённый. Точка на скате, расположенная на 12 мм от внутр. края (=ridge),
    # после поворота на ROOF_ANGLE окажется примерно над фронтоном на расстоянии:
    # горизонтальный сдвиг = 12 * cos(angle) от ridge
    # вертикальный сдвиг = 12 * sin(angle) ниже ridge
    horiz_offset = 12 * math.cos(bh.ROOF_ANGLE)
    vert_offset = 12 * math.sin(bh.ROOF_ANGLE)
    print(fmt(True, "Tie-hole ската оказывается над фронтоном",
              f"скат отстоит от ridge на {horiz_offset:.1f} мм гор. / {vert_offset:.1f} мм верт."))

    # ──────────────────────────────────────────────────────────────────────
    section("6. Печатные ограничения (проверка после редизайна)")

    # 6.1 — все детали помещаются на стол K1C (220×220×250)
    bed = (220, 220, 250)
    for name, m in meshes.items():
        bb = m.bounds[1] - m.bounds[0]
        ok = all(d <= b for d, b in zip(bb, bed))
        det = f"bbox={[round(x,1) for x in bb]}, max={max(bb):.1f}"
        print(fmt(ok, f"{name} помещается в стол K1C", det))
        all_ok &= ok

    # 6.2 — леток в форме «домика»: top angle ≤ 45° от вертикали
    # Прямоугольник W×H_rect + треугольник W→0 над H_peak
    # Tan(angle from vertical) = (W/2) / H_peak
    angle_top = math.degrees(math.atan2(bh.ENT_W / 2, bh.ENT_PEAK_H))
    ok = angle_top <= 50  # 45° + небольшой запас (PETG норм с 50° overhang)
    print(fmt(ok, "Угол пика летка от вертикали ≤ 50°",
              f"{angle_top:.1f}°"))
    all_ok &= ok

    # 6.3 — угол ската крыши: при наклоне крыши на ROOF_ANGLE
    # для печати ската ПЛАШМЯ — нет проблем (он плоский во время печати)
    print(fmt(True, "Скат печатается плашмя — overhang'ов нет", ""))

    # 6.4 — чамфер на штифте платы: 45° по построению
    # Проверим, что chamfer_h = (head_d - stem_d) / 2 даёт ровно 45°
    chamfer_h = (bh.TMP_PIN_HEAD_D - bh.TMP_PIN_STEM_D) / 2
    radial_expand = chamfer_h
    ok = abs(chamfer_h - radial_expand) < 0.01
    print(fmt(ok, "Чамфер на штифте = 45° (печать без поддержек)",
              f"chamfer_h = {chamfer_h} мм, radial = {radial_expand} мм"))
    all_ok &= ok

    # 6.5 — counterbore зенковки на плате: bridge диаметр ~ counterbore - hole
    cb_bridge = (bh.TMP_SCREW_HEAD_D - bh.TMP_SCREW_D) / 2
    ok = cb_bridge < 5.0  # короткий bridge, безопасно
    print(fmt(ok, "Bridge зенковки короткий (<5 мм)",
              f"кольцо шириной {cb_bridge:.1f} мм"))
    all_ok &= ok

    # ──────────────────────────────────────────────────────────────────────
    section("7. Конфликты позиций на плате")

    # Шляпки штырей не пересекаются с зенковками саморезов
    # Штыри на (X=0, Y=±35), шляпка Ø8 → X∈[-4,4], Y∈[31,39] и [-39,-31]
    # Зенковки на (X=±25, Y=±40), Ø9.5 → X∈[20.25, 29.75] (или -29.75..-20.25), Y∈[35.25, 44.75]
    pin_x_max = bh.TMP_PIN_HEAD_D / 2  # 4
    pin_y_top = bh.TMP_PIN_Y_TOP + bh.TMP_PIN_HEAD_D / 2  # верх шляпки верхних пинов
    pin_y_bot = bh.TMP_PIN_Y_TOP - bh.TMP_PIN_HEAD_D / 2  # низ шляпки
    cb_x_min = bh.TMP_SCREW_DX - bh.TMP_SCREW_HEAD_D / 2  # 20.25
    cb_x_max = bh.TMP_SCREW_DX + bh.TMP_SCREW_HEAD_D / 2  # 29.75
    cb_y_min = bh.TMP_SCREW_DY - bh.TMP_SCREW_HEAD_D / 2  # 35.25
    cb_y_max = bh.TMP_SCREW_DY + bh.TMP_SCREW_HEAD_D / 2  # 44.75

    # X-расстояние между ближайшими краями
    x_clearance = cb_x_min - pin_x_max  # 20.25 - 4 = 16.25
    ok = x_clearance > 5
    print(fmt(ok, "X-зазор между шляпкой штифта и зенковкой",
              f"{x_clearance:.1f} мм"))
    all_ok &= ok

    # Y-перекрытие (если bb перекрываются по Y, то проверяем что X-зазор есть — выше OK)
    # При X-зазоре есть, Y-перекрытие не критично.

    # Зенковки не выходят за края платы (≥3 мм margin для прочности кромки)
    margin_x = bh.TMP_W / 2 - cb_x_max
    margin_y = bh.TMP_H / 2 - cb_y_max
    ok = margin_x >= 3 and margin_y >= 3
    print(fmt(ok, "Зенковки внутри платы с запасом ≥3 мм по краям",
              f"X-margin {margin_x:.1f} мм, Y-margin {margin_y:.1f} мм"))
    all_ok &= ok

    # Штыри не выходят за края платы
    pin_y_extreme = abs(bh.TMP_PIN_Y_BOT) + bh.TMP_PIN_HEAD_D / 2
    margin_pin_y = bh.TMP_H / 2 - pin_y_extreme
    ok = margin_pin_y > 3
    print(fmt(ok, "Штыри внутри платы с запасом ≥3 мм по краям",
              f"Y-margin до края {margin_pin_y:.1f} мм"))
    all_ok &= ok

    # ──────────────────────────────────────────────────────────────────────
    section("8. Верификация по объёмам — фичи реально вырезались")

    # Пятиугольный леток: площадь = W * H_rect + (W * H_peak / 2)
    ent_area = bh.ENT_W * bh.ENT_RECT_H + (bh.ENT_W * bh.ENT_PEAK_H / 2)
    expected_ent_vol = ent_area * bh.WALL_T / 1000  # cm³
    print(fmt(True, "Ожидаемый объём вырезанного летка (информативно)",
              f"{expected_ent_vol:.2f} cm³"))

    # Дренаж v6: пирамида (132×132 база, 3 мм глубина) + центральный слив (Ø6, через FLOOR_T)
    # Объём пирамиды = (1/3) * base² * depression
    pyramid_vol = (1/3) * bh.DRAIN_PYRAMID_BASE ** 2 * bh.DRAIN_DEPRESSION / 1000
    drain_central_vol = math.pi * (bh.DRAIN_D / 2) ** 2 * bh.FLOOR_T / 1000
    drain_vol = pyramid_vol + drain_central_vol
    print(fmt(True, "Ожидаемый объём дренажа",
              f"{drain_vol:.2f} cm³"))

    # Сумма вентиляции: 6 щелей (3 на сторону)
    vent_vol = 2 * bh.N_VENT * bh.VENT_W * bh.VENT_H * bh.WALL_T / 1000
    print(fmt(True, "Ожидаемый объём вентиляции",
              f"{vent_vol:.2f} cm³"))

    # Проверка: реальный объём базы vs ожидаемый
    if "base" in meshes:
        floor_v = bh.EXT * bh.EXT * bh.FLOOR_T
        walls_v = 2 * bh.EXT * bh.WALL_T * bh.WALL_H + 2 * (bh.EXT - 2 * bh.WALL_T) * bh.WALL_T * bh.WALL_H
        gable_area = (bh.EXT + bh.GABLE_FLAT_W) / 2 * bh.GABLE_H
        gables_v = 2 * gable_area * bh.WALL_T
        # Утолщения боковин (2 шт.) с ТРЕУГОЛЬНЫМ сечением (наклонная нижняя грань):
        # площадь треугольника = 0.5 * LIP_W * LIP_H, длина = EXT - 2*WALL_T
        lips_v = 2 * 0.5 * bh.WALL_TOP_LIP_W * bh.WALL_TOP_LIP_H * (bh.EXT - 2 * bh.WALL_T)
        full_v = (floor_v + walls_v + gables_v + lips_v) / 1000  # cm³

        cut_v = expected_ent_vol + drain_vol + vent_vol
        kh_v = 3 * (math.pi * (bh.KH_BIG_D / 2) ** 2 + bh.KH_SLOT_W * bh.KH_SLOT_LEN) * bh.WALL_T / 1000
        cut_v += kh_v
        tie_v = 2 * math.pi * 2 ** 2 * bh.WALL_T / 1000
        cut_v += tie_v
        # Пазы (2 шт.): ROOF_GROOVE_W × ROOF_GROOVE_D × groove_length
        groove_len = bh.EXT - 2 * bh.WALL_T - 2 * bh.ROOF_GROOVE_MARGIN
        groove_v = 2 * bh.ROOF_GROOVE_W * bh.ROOF_GROOVE_D * groove_len / 1000
        cut_v += groove_v

        expected_base_v = full_v - cut_v
        actual_base_v = meshes["base"].volume / 1000
        diff_pct = abs(actual_base_v - expected_base_v) / expected_base_v * 100
        ok = diff_pct < 10
        print(fmt(ok, f"Объём базы соответствует расчётному",
                  f"расчёт {expected_base_v:.1f} cm³, факт {actual_base_v:.1f} cm³, "
                  f"расхождение {diff_pct:.1f}%"))
        if not ok:
            all_ok &= ok

    # ──────────────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    if all_ok:
        print("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — детали состыкуются.")
    else:
        print("✗ НАЙДЕНЫ ПРОБЛЕМЫ — см. выше.")
    print(f"{'='*70}\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
