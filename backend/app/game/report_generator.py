"""
PDF генератор отчётов по сотруднику.
Кириллица через системный Arial. Фоллбэк — транслит.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.db.models import Achievement, QuestStatus, SafetyCheck, User, UserAchievement, UserQuestProgress
from app.game.xp_engine import level_title

C_ACCENT  = (0,   170, 255)
C_SUCCESS = (0,   200, 100)
C_DANGER  = (200, 50,  50)
C_GRAY    = (100, 120, 140)
C_WHITE   = (255, 255, 255)
C_LIGHT   = (230, 235, 245)
C_DARK    = (30,  40,  55)

_TR = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
    'и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
    'щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}

def _t(s: str) -> str:
    out = []
    for c in s:
        lo = c.lower()
        if lo in _TR:
            tr = _TR[lo]
            out.append(tr[0].upper() + tr[1:] if c.isupper() and tr else tr)
        else:
            try:
                c.encode('latin-1')
                out.append(c)
            except Exception:
                out.append('?')
    return ''.join(out)

def _fd(dt):
    if not dt: return "-"
    if dt.tzinfo: dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y")

def _fdt(dt):
    if not dt: return "-"
    if dt.tzinfo: dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y %H:%M")


class PDF(FPDF):
    _uni = False

    def _setup(self, font_dir: str = ""):
        # Ищем шрифт с поддержкой кириллицы
        candidates = [
            # Сначала проверяем папку проекта (backend/fonts/)
            os.path.join(font_dir, "DejaVuSans.ttf"),
            # Windows - Arial
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\Arial.ttf",
            r"C:\Windows\Fonts\ARIAL.TTF",
            # Windows - другие шрифты с кириллицей
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
        for p in candidates:
            if p and os.path.exists(p):
                try:
                    self.add_font("U","",p); self.add_font("U","B",p); self.add_font("U","I",p)
                    self._uni = True; break
                except Exception: pass

    def _f(self, style="", size=10):
        self.set_font("U" if self._uni else "Helvetica", style, size)

    def _s(self, text): return text if self._uni else _t(str(text))

    def header(self):
        self.set_fill_color(*C_ACCENT); self.rect(0,0,210,4,"F")

    def footer(self):
        self.set_y(-15); self._f("I",8); self.set_text_color(*C_GRAY)
        self.cell(0,10,f"FirstShift | {datetime.now().strftime('%d.%m.%Y %H:%M')} | Стр. {self.page_no()}",align="C")

    def sec(self, title):
        self.ln(4); self.set_fill_color(*C_DARK); self.set_text_color(*C_WHITE)
        self._f("B",10); self.cell(0,8,f"  {self._s(title)}",fill=True,ln=True)
        self.ln(2); self.set_text_color(0,0,0)

    def kv(self, k, v, fill=False):
        if fill: self.set_fill_color(*C_LIGHT)
        self._f("B",9); self.set_text_color(*C_GRAY)
        self.cell(55,6,self._s(k),fill=fill)
        self._f("",9); self.set_text_color(0,0,0)
        self.cell(0,6,self._s(v),fill=fill,ln=True)

    def pbar(self, pct, label=""):
        x,y,w,h = self.get_x(),self.get_y(),120,5
        self.set_fill_color(200,210,220); self.rect(x,y,w,h,"F")
        fw = w*min(pct,1.0)
        self.set_fill_color(*(C_SUCCESS if pct>=1.0 else C_ACCENT))
        if fw>0: self.rect(x,y,fw,h,"F")
        self.set_xy(x+w+4,y-1); self._f("B",9); self.set_text_color(*C_GRAY)
        self.cell(40,7,self._s(f"{int(pct*100)}%  {label}"))
        self.ln(h+3); self.set_text_color(0,0,0)

    def thead(self, cols):
        self.set_fill_color(*C_DARK); self.set_text_color(*C_WHITE); self._f("B",9)
        for lbl,w in cols: self.cell(w,7,self._s(lbl),fill=True)
        self.ln(); self.set_text_color(0,0,0)

    def trow(self, cells, i=0):
        if i%2==0: self.set_fill_color(*C_LIGHT)
        fill = i%2==0; self._f("",8)
        for txt,w in cells: self.cell(w,6,self._s(str(txt)),fill=fill)
        self.ln()


def generate_employee_report(db: Session, user: User, period_days: int = 30) -> bytes:
    # Определяем путь к папке с шрифтами (backend/fonts/ рядом с этим файлом)
    _font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
    pdf = PDF(); pdf._setup(_font_dir); pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Шапка
    pdf.ln(6); pdf._f("B",20); pdf.set_text_color(*C_DARK)
    pdf.cell(0,12,pdf._s(user.display_name or user.username),ln=True)
    pdf._f("",10); pdf.set_text_color(*C_GRAY)
    roles = {"employee":"Сотрудник","mentor":"Наставник","hr":"HR","admin":"Администратор"}
    pdf.cell(0,6,f"@{user.username}  |  {roles.get(user.role,user.role)}  |  {_fd(user.created_at)}",ln=True)
    pdf.ln(3)
    pdf.set_draw_color(*C_ACCENT); pdf.set_line_width(0.5)
    pdf.line(10,pdf.get_y(),200,pdf.get_y()); pdf.ln(4)

    # Профиль
    pdf.sec("Профиль")
    pdf.kv("Уровень:", f"{user.level} - {pdf._s(level_title(user.level))}", fill=True)
    pdf.kv("Итого XP:", str(user.total_xp))
    pdf.kv("Последняя активность:", _fdt(user.last_active_at), fill=True)

    tq = db.query(UserQuestProgress).filter(UserQuestProgress.user_id==user.id).count()
    dq = db.query(UserQuestProgress).filter(
        UserQuestProgress.user_id==user.id,
        UserQuestProgress.status==QuestStatus.COMPLETED.value).count()
    pdf.ln(3); pdf._f("B",9); pdf.set_text_color(*C_GRAY)
    pdf.cell(55,6,pdf._s("Прогресс онбординга:")); pdf.set_text_color(0,0,0); pdf.ln(6)
    pdf.set_x(65); pdf.pbar(dq/tq if tq else 0, f"{dq}/{tq}")

    # Квесты
    pdf.sec("Квесты")
    pl = db.query(UserQuestProgress).filter(UserQuestProgress.user_id==user.id).join(UserQuestProgress.quest).all()
    ST = {"completed":"Выполнен","active":"Активен","available":"Доступен","locked":"Заблокирован","failed":"Провален"}
    if pl:
        pdf.thead([("Квест",80),("Статус",38),("XP",22),("Дата",50)])
        for i,p in enumerate(pl):
            t = (p.quest.title[:37]+"..") if len(p.quest.title)>39 else p.quest.title
            pdf.trow([(pdf._s(t),80),(ST.get(p.status,p.status),38),
                      (f"+{p.quest.xp_reward}" if p.status=="completed" else "-",22),
                      (_fd(p.completed_at),50)], i)
    else:
        pdf._f("I",9); pdf.set_text_color(*C_GRAY); pdf.cell(0,6,"Нет данных",ln=True); pdf.set_text_color(0,0,0)

    # Safety Check
    pdf.sec(f"Safety Check — последние {period_days} дн.")
    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    checks = db.query(SafetyCheck).filter(SafetyCheck.user_id==user.id,SafetyCheck.timestamp>=since).order_by(SafetyCheck.timestamp.desc()).all()
    if checks:
        passed = sum(1 for c in checks if c.passed)
        pdf._f("",9); pdf.cell(0,6,f"Всего: {len(checks)}   Успешных: {passed}   Нарушений: {len(checks)-passed}",ln=True); pdf.ln(2)
        pdf.thead([("Дата и время",58),("Результат",35),("Каска",28),("Жилет",28),("Отсутствует",35)])
        for i,c in enumerate(checks):
            miss = ", ".join(json.loads(c.missing_items or "[]")) or "-"
            res  = "✓ Пройдена" if c.passed else "Нарушение"
            saved_color = None
            if not c.passed:
                pdf.set_text_color(*C_DANGER)
            else:
                pdf.set_text_color(0,150,80)
            pdf.trow([(_fdt(c.timestamp),58),(res,35),
                      ("Да" if c.helmet else "Нет",28),
                      ("Да" if c.vest else "Нет",28),(miss,41)], i)
            pdf.set_text_color(0,0,0)
    else:
        pdf._f("I",9); pdf.set_text_color(*C_GRAY)
        pdf.cell(0,6,f"Нет данных за последние {period_days} дней",ln=True); pdf.set_text_color(0,0,0)

    # Ачивки
    pdf.sec("Достижения")
    al = db.query(UserAchievement).filter(UserAchievement.user_id==user.id).join(UserAchievement.achievement).order_by(UserAchievement.unlocked_at.desc()).all()
    ta = db.query(Achievement).count()
    if al:
        pdf._f("",9); pdf.set_text_color(*C_GRAY)
        pdf.cell(0,6,f"Разблокировано: {len(al)} из {ta}",ln=True); pdf.set_text_color(0,0,0); pdf.ln(2)
        pdf.thead([("Достижение",100),("Бонус XP",40),("Дата",50)])
        for i,ua in enumerate(al):
            pdf.trow([(pdf._s(ua.achievement.title),100),(f"+{ua.achievement.xp_bonus}",40),(_fd(ua.unlocked_at),50)],i)
    else:
        pdf._f("I",9); pdf.set_text_color(*C_GRAY); pdf.cell(0,6,"Нет",ln=True); pdf.set_text_color(0,0,0)

    # Итог
    pdf.ln(8); pdf.set_draw_color(*C_ACCENT)
    pdf.line(10,pdf.get_y(),200,pdf.get_y()); pdf.ln(4)
    pdf._f("I",8); pdf.set_text_color(*C_GRAY)
    pdf.cell(0,6,f"@{user.username} | Период: {period_days} дн. | FirstShift v0.2",ln=True)

    buf = BytesIO(); pdf.output(buf); return buf.getvalue()
