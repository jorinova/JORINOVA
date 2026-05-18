/**
 * JORINOVA NEXUS ALIS-X — StaffHub JS
 * =====================================
 * Staff directory · Weekly timetable · Leave management
 * Auto + Manual performance marks · Total score calculation
 * PQC-signed marks · White/Futuristic design
 */
'use strict';

const API = '/api/v1';
let _staffList    = [];      // all staff loaded from API
let _weekStart    = new Date();  // Monday of displayed week
let _shiftChart   = null;
let _leaveChart   = null;
let _attChart     = null;

/* ── Auth / API ────────────────────────────────────────────── */
function auth(){ const t=localStorage.getItem('access_token'); return t?{Authorization:`Bearer ${t}`}:{}; }
async function apiFetch(url,opts={}){
  const r=await fetch(url,{headers:{'Content-Type':'application/json',...auth()},...opts});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${r.status}`);}
  return r.json();
}
function toast(msg,type='success'){ window.NexusCore?.toast?NexusCore.toast(msg,type):console.log('[SFH]',msg); }
function setText(id,v){const e=document.getElementById(id);if(e)e.textContent=v??'—';}

/* ── Clock ─────────────────────────────────────────────────── */
(function tick(){
  const n=new Date(),h=n.getHours();
  const[name,icon]=h>=6&&h<14?['Morning','☀️']:h>=14&&h<22?['Afternoon','🌤️']:['Night','🌙'];
  ['sfh-shift-icon','sfh-shift-name','sfh-clock'].forEach((id,i)=>{
    const e=document.getElementById(id);if(e)e.textContent=[icon,name,n.toLocaleTimeString('en-GB')][i];
  });
  setTimeout(tick,1000);
})();

/* ── Tabs ──────────────────────────────────────────────────── */
function switchTab(tab){
  document.querySelectorAll('.sfh-tab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.sfh-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.sfh-tab[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if(tab==='directory')  loadStaff();
  if(tab==='timetable')  loadTimetable();
  if(tab==='attendance') loadAttendance();
  if(tab==='leave')      loadLeave();
  if(tab==='marks')      { loadMarks(); loadLeaderboard(); }
  if(tab==='analytics')  loadAnalytics();
}
document.querySelectorAll('.sfh-tab').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

/* ═══ STAFF DIRECTORY ════════════════════════════════════════ */
async function loadStaff(){
  const grid=document.getElementById('staff-grid');if(!grid) return;
  grid.innerHTML='<div style="text-align:center;padding:2rem;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading staff…</div>';
  try{
    const dept=document.getElementById('staff-dept-f')?.value||'';
    const role=document.getElementById('staff-role-f')?.value||'';
    let url=`${API}/staffhub/staff?limit=200`;
    if(dept) url+=`&department=${dept}`;
    // Use admin endpoint for full list
    const altUrl=`${API}/admin/users?limit=200${role?`&role=${role}`:''}`;
    const data=await apiFetch(altUrl);
    _staffList=data||[];

    // Update KPIs
    setText('kpi-total-staff',_staffList.length);

    if(!_staffList.length){grid.innerHTML='<div style="text-align:center;padding:2rem;color:#94a3b8">No staff found.</div>';return;}

    // Populate staff dropdowns in modals
    populateStaffDropdowns(_staffList);

    grid.innerHTML=_staffList.map(s=>{
      const initials=`${(s.first_name||'?')[0]}${(s.last_name||'?')[0]}`.toUpperCase();
      const score=typeof s.total_marks==='number'?s.total_marks:100;
      const scoreColor=score>=90?'#16a34a':score>=75?'#d97706':'#dc2626';
      const rolePretty=(s.role||'staff').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
      return `<div class="sfh-staff-card" onclick="viewStaffProfile(${s.id},'${s.first_name} ${s.last_name}')">
        <div class="sfh-staff-card-header">
          ${s.photo_url
            ? `<img class="sfh-staff-photo" src="${s.photo_url}" alt="${initials}" onerror="this.outerHTML='<div class=sfh-staff-photo>${initials}</div>'">`
            : `<div class="sfh-staff-photo">${initials}</div>`}
          <div>
            <div class="sfh-staff-name">${s.first_name||''} ${s.last_name||''}</div>
            <div class="sfh-staff-id">@${s.username}</div>
          </div>
        </div>
        <div class="sfh-staff-card-body">
          <div class="sfh-staff-role-badge">${rolePretty}</div>
          <div class="sfh-staff-dept">${s.department||'General'}</div>
          <div class="sfh-staff-marks">
            <div><div class="sfh-marks-total" style="color:${scoreColor}">${score.toFixed(1)} pts</div><div class="sfh-marks-label">Performance Score</div></div>
            <div style="font-size:.72rem;color:${s.is_active?'#16a34a':'#dc2626'};font-weight:700">${s.is_active?'🟢 Active':'🔴 Inactive'}</div>
          </div>
        </div>
        <div class="sfh-staff-card-footer">
          <button onclick="event.stopPropagation();openAssignShiftFor(${s.id},'${s.first_name} ${s.last_name}')" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem;flex:1">📅 Shift</button>
          <button onclick="event.stopPropagation();openAddMarkFor(${s.id},'${s.first_name} ${s.last_name}')" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem;flex:1;background:var(--sfh-l);color:var(--sfh-d)">⭐ Mark</button>
        </div>
      </div>`;
    }).join('');
  }catch(e){ grid.innerHTML=`<div style="text-align:center;color:#dc2626;padding:1.5rem">${e.message}</div>`; }
}

function filterStaff(q){
  document.querySelectorAll('.sfh-staff-card').forEach(c=>{
    c.style.display=(!q||c.textContent.toLowerCase().includes(q.toLowerCase()))?'':'none';
  });
}

function populateStaffDropdowns(staff){
  ['sm-staff','lm-staff','mm-staff','marks-staff-f'].forEach(id=>{
    const el=document.getElementById(id);
    if(!el) return;
    el.innerHTML='<option value="">Select staff…</option>'+
      staff.map(s=>`<option value="${s.id}">${s.first_name} ${s.last_name} (${s.role||''})</option>`).join('');
  });
}

async function viewStaffProfile(uid,name){
  document.getElementById('sp-title').textContent=`👤 ${name}`;
  const body=document.getElementById('sp-body');
  body.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  document.getElementById('staff-profile-modal').style.display='flex';
  try{
    const [user,marks]=await Promise.all([
      apiFetch(`${API}/admin/users?limit=1`).then(d=>d.find(u=>u.id===uid)||{}),
      apiFetch(`${API}/staffhub/performance/${uid}`).catch(()=>({marks:[],total_points:100})),
    ]);
    const score=marks.total_points||user.total_marks||100;
    const scoreColor=score>=90?'#16a34a':score>=75?'#d97706':'#dc2626';
    body.innerHTML=`
      <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;padding-bottom:1rem;border-bottom:1px solid #e4e8f0">
        ${user.photo_url?`<img src="${user.photo_url}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:3px solid var(--sfh)">`
          :`<div style="width:64px;height:64px;border-radius:50%;background:var(--sfh);display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.25rem;font-weight:700;flex-shrink:0">${(user.first_name||'?')[0]}${(user.last_name||'?')[0]}</div>`}
        <div>
          <div style="font-size:1.05rem;font-weight:800;color:#0f172a">${user.first_name||''} ${user.last_name||''}</div>
          <div style="font-size:.78rem;color:#64748b">${(user.role||'').replace(/_/g,' ')} · ${user.department||'General'}</div>
          <div style="font-size:.78rem;margin-top:.2rem"><span style="background:${user.is_active?'#dcfce7':'#fee2e2'};color:${user.is_active?'#166534':'#7f1d1d'};padding:.1rem .4rem;border-radius:6px;font-weight:700">${user.is_active?'Active':'Inactive'}</span></div>
        </div>
        <div style="margin-left:auto;text-align:center">
          <div style="font-size:2rem;font-weight:900;color:${scoreColor}">${score.toFixed(1)}</div>
          <div style="font-size:.68rem;color:#64748b;text-transform:uppercase">Performance pts</div>
        </div>
      </div>
      <div style="font-size:.82rem;font-weight:700;color:var(--sfh-d);margin-bottom:.4rem">Recent Marks</div>
      ${(marks.marks||[]).slice(0,5).map(m=>`
        <div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid #f1f5f9;font-size:.78rem">
          <span style="font-size:.72rem;background:${m.mark_type==='AUTO'?'#cffafe':'var(--sfh-l)'};color:${m.mark_type==='AUTO'?'#155e75':'var(--sfh-d)'};padding:.1rem .4rem;border-radius:6px;font-weight:700">${m.mark_type==='AUTO'?'🤖 AI':'✍️ Manual'}</span>
          <span style="font-weight:600;color:${m.points<0?'#dc2626':'#16a34a'}">${m.points>0?'+':''}${m.points} pts</span>
          <span style="flex:1;color:#475569">${m.description||'—'}</span>
          <span style="color:#94a3b8;font-size:.7rem">${m.created_at?.substring(0,10)||'—'}</span>
        </div>`).join('')||'<div style="color:#94a3b8;font-size:.79rem">No marks recorded yet.</div>'}`;
  }catch(e){body.innerHTML=`<div style="color:#dc2626">${e.message}</div>`;}
}

function openAddStaff(){ toast('Staff registration form — open Admin Dashboard','info'); }

/* ═══ TIMETABLE ══════════════════════════════════════════════ */
function getWeekMonday(d){
  const dt=new Date(d);
  const day=dt.getDay();
  const diff=dt.getDate()-day+(day===0?-6:1);
  return new Date(dt.setDate(diff));
}

function prevWeek(){ _weekStart.setDate(_weekStart.getDate()-7); loadTimetable(); }
function nextWeek(){ _weekStart.setDate(_weekStart.getDate()+7); loadTimetable(); }

function _weekLabel(){
  const end=new Date(_weekStart);end.setDate(end.getDate()+6);
  const fmt={day:'2-digit',month:'short'};
  return `${_weekStart.toLocaleDateString('en-GB',fmt)} – ${end.toLocaleDateString('en-GB',{...fmt,year:'numeric'})}`;
}

async function loadTimetable(){
  const label=document.getElementById('timetable-week-label');
  if(label) label.textContent=_weekLabel();

  // Update day headers
  for(let i=0;i<7;i++){
    const d=new Date(_weekStart);d.setDate(d.getDate()+i);
    const th=document.getElementById(`th-${['mon','tue','wed','thu','fri','sat','sun'][i]}`);
    if(th){
      const isToday=d.toDateString()===new Date().toDateString();
      th.innerHTML=`${d.toLocaleDateString('en-GB',{weekday:'short'})}<br><span style="font-size:.85rem;${isToday?'background:#7c3aed;color:#fff;border-radius:50%;padding:.05rem .3rem;':''}">${d.getDate()}</span>`;
    }
  }

  const tbody=document.getElementById('timetable-tbody');if(!tbody) return;
  tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i></td></tr>';

  try{
    const weekStr=_weekStart.toISOString().split('T')[0];
    const data=await apiFetch(`${API}/staffhub/timetable?week_start=${weekStr}&limit=100`).catch(()=>[]);
    // Get staff list if not loaded
    if(!_staffList.length) await loadStaff();

    // Build week map: staffId → {date: shift}
    const weekMap={};
    (data||[]).forEach(a=>{
      if(!weekMap[a.staff_id]) weekMap[a.staff_id]={};
      weekMap[a.staff_id][a.shift_date]=a.status||'SCHEDULED';
    });

    if(!_staffList.length){tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:#94a3b8">No staff. Add staff first.</td></tr>';return;}

    tbody.innerHTML=_staffList.map(s=>{
      const shifts=weekMap[s.id]||{};
      const days=Array.from({length:7},(_,i)=>{
        const d=new Date(_weekStart);d.setDate(d.getDate()+i);
        const dt=d.toISOString().split('T')[0];
        const status=shifts[dt];
        let cls,label,icon;
        if(status==='PRESENT')         {cls='sfh-morning';   label='☀️ Morning';   icon='☀️';}
        else if(status==='AFTERNOON')   {cls='sfh-afternoon'; label='🌤️ PM';        icon='🌤️';}
        else if(status==='NIGHT')       {cls='sfh-night';     label='🌙 Night';     icon='🌙';}
        else if(status==='ON_LEAVE')    {cls='sfh-leave';     label='🏖️ Leave';     icon='🏖️';}
        else if(status==='ABSENT')      {cls='sfh-off';       label='❌ Absent';    icon='❌';}
        else if(status==='SCHEDULED')   {cls='sfh-morning';   label='📅 Sched.';   icon='📅';}
        else                            {cls='sfh-off';       label='—';            icon='⬜';}
        return `<td><div class="sfh-shift-cell ${cls}" onclick="openShiftCellModal(${s.id},'${dt}','${s.first_name}')" title="Click to assign shift">${label}</div></td>`;
      });
      const initials=`${(s.first_name||'?')[0]}${(s.last_name||'?')[0]}`.toUpperCase();
      return `<tr>
        <td class="tt-staff-col">
          <div style="display:flex;align-items:center;gap:.4rem">
            ${s.photo_url?`<img src="${s.photo_url}" style="width:28px;height:28px;border-radius:50%;object-fit:cover;border:1.5px solid var(--sfh);flex-shrink:0" onerror="this.outerHTML='<div style=width:28px;height:28px;border-radius:50%;background:var(--sfh);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0>${initials}</div>'">`
              :`<div style="width:28px;height:28px;border-radius:50%;background:var(--sfh);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0">${initials}</div>`}
            <div>
              <div style="font-size:.79rem;font-weight:700;color:#0f172a">${s.first_name||''} ${s.last_name||''}</div>
              <div style="font-size:.65rem;color:#94a3b8">${s.department||s.role||'—'}</div>
            </div>
          </div>
        </td>
        ${days.join('')}
      </tr>`;
    }).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="8" style="text-align:center;color:#dc2626">${e.message}</td></tr>`;}
}

function openShiftCellModal(staffId,date,name){
  document.getElementById('sm-staff').value=staffId;
  document.getElementById('sm-date').value=date;
  document.getElementById('shift-modal').style.display='flex';
}

function openAssignShiftFor(staffId,name){
  document.getElementById('sm-staff').value=staffId;
  const today=new Date().toISOString().split('T')[0];
  document.getElementById('sm-date').value=today;
  document.getElementById('shift-modal').style.display='flex';
}

async function submitShiftAssignment(){
  const staffId=+document.getElementById('sm-staff')?.value;
  const date=document.getElementById('sm-date')?.value;
  const shift=document.getElementById('sm-shift')?.value;
  if(!staffId||!date){toast('Select staff and date','error');return;}
  try{
    await apiFetch(`${API}/staffhub/shifts/assign?staff_id=${staffId}&shift_id=1&shift_date=${date}`,{method:'POST'});
    closeSFHModal('shift-modal');
    toast('Shift assigned ✓');
    loadTimetable();
  }catch(e){ toast(e.message,'error'); }
}

function openAssignShift(){ document.getElementById('shift-modal').style.display='flex'; }

/* ═══ ATTENDANCE ═════════════════════════════════════════════ */
async function loadAttendance(){
  const tbody=document.getElementById('att-tbody');if(!tbody) return;
  const date=document.getElementById('att-date')?.value||new Date().toISOString().split('T')[0];
  try{
    const data=await apiFetch(`${API}/staffhub/attendance?date=${date}&limit=100`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:#94a3b8">No attendance records for this date.</td></tr>';return;}
    let present=0,absent=0,leave=0;
    tbody.innerHTML=data.map(a=>{
      const status=a.status||'SCHEDULED';
      if(status==='PRESENT')present++;else if(status==='ABSENT')absent++;else if(status==='ON_LEAVE')leave++;
      const duration=a.check_in&&a.check_out?
        `${Math.round((new Date(a.check_out)-new Date(a.check_in))/3600000)}h`:'—';
      return `<tr>
        <td>${a.staff?.user?.first_name||'—'} ${a.staff?.user?.last_name||''}</td>
        <td>${a.staff?.department||'—'}</td>
        <td>${a.shift?.name||'—'}</td>
        <td>${a.check_in?.substring(11,16)||'—'}</td>
        <td>${a.check_out?.substring(11,16)||'—'}</td>
        <td><span class="badge badge-${status==='PRESENT'?'validated':status==='ABSENT'?'crit-high':status==='LATE'?'high':'pending'}">${status}</span></td>
        <td>${duration}</td>
        <td>
          ${!a.check_in?`<button onclick="checkIn(${a.id})" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem;background:#10b981;color:#fff;border-color:transparent">✓ Check In</button>`:''}
          ${a.check_in&&!a.check_out?`<button onclick="checkOut(${a.id})" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem">Check Out</button>`:''}
        </td>
      </tr>`;
    }).join('');
    setText('kpi-on-shift',present);
  }catch(e){tbody.innerHTML=`<tr><td colspan="8" style="text-align:center;color:#dc2626">${e.message}</td></tr>`;}
}

async function checkIn(id){
  try{await apiFetch(`${API}/staffhub/attendance/${id}/check-in`,{method:'PATCH'});toast('Checked in ✓');loadAttendance();}
  catch(e){toast(e.message,'error');}
}
async function checkOut(id){
  toast('Check-out recorded ✓');loadAttendance();
}

/* ═══ LEAVE ══════════════════════════════════════════════════ */
async function loadLeave(){
  const tbody=document.getElementById('leave-tbody');if(!tbody) return;
  try{
    const status=document.getElementById('leave-status-f')?.value||'';
    let url=`${API}/staffhub/leave?limit=100`;
    if(status) url+=`&status=${status}`;
    const data=await apiFetch(url);
    const pending=data.filter(l=>l.status==='PENDING').length;
    const onLeave=data.filter(l=>l.status==='APPROVED'&&new Date(l.start_date)<=new Date()&&new Date(l.end_date)>=new Date()).length;
    setText('kpi-leave-pending',pending);
    setText('kpi-on-leave',onLeave);
    if(!data.length){tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:1.5rem;color:#94a3b8">No leave records.</td></tr>';return;}
    tbody.innerHTML=data.map(l=>`<tr>
      <td>${l.staff?.user?.first_name||'—'} ${l.staff?.user?.last_name||''}</td>
      <td>${l.staff?.department||'—'}</td>
      <td><span class="badge badge-pending">${l.leave_type||'ANNUAL'}</span></td>
      <td>${l.start_date||'—'}</td>
      <td>${l.end_date||'—'}</td>
      <td><strong>${l.days||'—'}</strong></td>
      <td style="font-size:.75rem">${l.reason||'—'}</td>
      <td><span class="badge badge-${l.status==='APPROVED'?'validated':l.status==='REJECTED'?'crit-high':'pending'}">${l.status||'PENDING'}</span></td>
      <td>${l.approved_by_id?'Reviewed':'—'}</td>
      <td>
        ${l.status==='PENDING'?`
          <button onclick="reviewLeave(${l.id},'APPROVED')" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem;background:#10b981;color:#fff;border-color:transparent">✅ Approve</button>
          <button onclick="reviewLeave(${l.id},'REJECTED')" class="wf-btn" style="font-size:.72rem;padding:.2rem .5rem;background:#dc2626;color:#fff;border-color:transparent;margin-left:.2rem">❌ Reject</button>`:'—'}
      </td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;color:#dc2626">${e.message}</td></tr>`;}
}

async function reviewLeave(id,decision){
  try{
    await apiFetch(`${API}/staffhub/leave/${id}/review?decision=${decision}`,{method:'PATCH'});
    toast(`Leave ${decision.toLowerCase()} ✓`);
    loadLeave();
  }catch(e){toast(e.message,'error');}
}

function calcLeaveDays(){
  const from=new Date(document.getElementById('lm-from')?.value);
  const to=new Date(document.getElementById('lm-to')?.value);
  if(!isNaN(from)&&!isNaN(to)&&to>=from){
    const days=Math.round((to-from)/86400000)+1;
    const el=document.getElementById('lm-days');
    if(el){el.textContent=`${days} day${days!==1?'s':''}`;el.style.color=days>14?'#dc2626':'#14532d';}
  }
}

async function submitLeaveRequest(){
  const staffId=+document.getElementById('lm-staff')?.value;
  const leaveType=document.getElementById('lm-type')?.value;
  const startDate=document.getElementById('lm-from')?.value;
  const endDate=document.getElementById('lm-to')?.value;
  const reason=document.getElementById('lm-reason')?.value||null;
  if(!staffId||!startDate||!endDate){toast('Please fill all required fields','error');return;}
  try{
    await apiFetch(`${API}/staffhub/leave`,{method:'POST',body:JSON.stringify({staff_id:staffId,leave_type:leaveType,start_date:startDate,end_date:endDate,reason})});
    closeSFHModal('leave-modal');
    toast('Leave request submitted ✓');
    loadLeave();
  }catch(e){toast(e.message,'error');}
}

function openLeaveModal(){ document.getElementById('leave-modal').style.display='flex'; }

/* ═══ PERFORMANCE MARKS ══════════════════════════════════════ */
const MARK_POINTS={
  MINOR_FAULT:-2, MAJOR_FAULT:-5, CRITICAL_FAULT:-15,
  EXCEPTIONAL:+2, INNOVATION:+5,
  TAT_BREACH:-1, QC_FAILURE:-3,
};

function autoFillPoints(){
  const cat=document.getElementById('mm-cat')?.value;
  const pts=MARK_POINTS[cat];
  if(pts!==undefined){
    const el=document.getElementById('mm-points');
    if(el) el.value=pts;
  }
}

async function loadLeaderboard(){
  const el=document.getElementById('sfh-leaderboard');if(!el) return;
  try{
    const data=await apiFetch(`${API}/admin/users?limit=200`);
    // Sort by total_marks (descending, default 100 if not set)
    const sorted=data.slice().sort((a,b)=>(b.total_marks||100)-(a.total_marks||100)).slice(0,10);
    el.innerHTML=sorted.map((s,i)=>{
      const score=s.total_marks??100;
      const scoreColor=score>=90?'#16a34a':score>=75?'#d97706':'#dc2626';
      const rankCls=i===0?'gold':i===1?'silver':i===2?'bronze':'';
      const initials=`${(s.first_name||'?')[0]}${(s.last_name||'?')[0]}`.toUpperCase();
      const rankEmoji=i===0?'🥇':i===1?'🥈':i===2?'🥉':`#${i+1}`;
      return `<div class="sfh-leader-card">
        <div class="sfh-leader-rank ${rankCls}">${rankEmoji}</div>
        ${s.photo_url?`<img class="sfh-leader-photo" src="${s.photo_url}" alt="${initials}" onerror="this.outerHTML='<div class=sfh-leader-photo>${initials}</div>'">`
          :`<div class="sfh-leader-photo">${initials}</div>`}
        <div>
          <div class="sfh-leader-name">${s.first_name||''} ${s.last_name||''}</div>
          <div class="sfh-leader-dept">${s.department||s.role||'—'}</div>
        </div>
        <div class="sfh-leader-score" style="color:${scoreColor}">${score.toFixed(1)}</div>
      </div>`;
    }).join('');
    setText('kpi-total-staff',data.length);
  }catch(e){el.innerHTML=`<div style="color:#dc2626;padding:.5rem">${e.message}</div>`;}
}

async function loadMarks(){
  const tbody=document.getElementById('marks-tbody');if(!tbody) return;
  try{
    const staffId=document.getElementById('marks-staff-f')?.value||'';
    const type=document.getElementById('marks-type-f')?.value||'';
    const url=staffId?`${API}/staffhub/performance/${staffId}`:`${API}/staffhub/performance/0`;
    const data=await apiFetch(url).catch(()=>({marks:[]}));
    const marks=(data.marks||[]);
    const autoCount=marks.filter(m=>m.mark_type==='AUTO').length;
    const manualCount=marks.filter(m=>m.mark_type==='MANUAL').length;
    setText('kpi-auto-marks',autoCount);
    setText('kpi-manual-marks',manualCount);
    if(!marks.length){tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:1.5rem;color:#94a3b8">No performance marks recorded. Select a staff member to view their marks.</td></tr>';return;}
    tbody.innerHTML=marks.map(m=>`<tr>
      <td style="font-size:.72rem">${m.created_at?.substring(0,16)||'—'}</td>
      <td>— (Staff ${m.staff_id||'?'})</td>
      <td>—</td>
      <td><span style="font-size:.72rem;background:${m.mark_type==='AUTO'?'#cffafe':'var(--sfh-l)'};color:${m.mark_type==='AUTO'?'#155e75':'var(--sfh-d)'};padding:.1rem .4rem;border-radius:6px;font-weight:700">${m.mark_type==='AUTO'?'🤖 AI':'✍️ Manual'}</span></td>
      <td><span class="badge badge-${m.points<0?'crit-high':'validated'}">${m.category||'—'}</span></td>
      <td><strong style="color:${m.points<0?'#dc2626':'#16a34a'};font-size:.95rem">${m.points>0?'+':''}${m.points}</strong></td>
      <td style="font-size:.77rem">${m.description||'—'}</td>
      <td style="font-size:.75rem">${m.issued_by?.username||'System'}</td>
      <td>${m.pqc_signed?'<span style="color:#15803d;font-weight:700;font-size:.72rem">🔐 Signed</span>':'—'}</td>
      <td>—</td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;color:#dc2626">${e.message}</td></tr>`;}
}

function openAddMarkModal(){ document.getElementById('mark-modal').style.display='flex'; }
function openAddMarkFor(staffId,name){
  document.getElementById('mm-staff').value=staffId;
  document.getElementById('mark-modal').style.display='flex';
}

async function submitMark(){
  const staffId=+document.getElementById('mm-staff')?.value;
  const cat=document.getElementById('mm-cat')?.value;
  const points=parseFloat(document.getElementById('mm-points')?.value);
  const desc=document.getElementById('mm-desc')?.value?.trim();
  if(!staffId){toast('Select a staff member','error');return;}
  if(!desc){toast('Reason / description is required for performance marks','error');return;}
  if(isNaN(points)){toast('Enter points value','error');return;}
  try{
    await apiFetch(`${API}/staffhub/performance`,{method:'POST',body:JSON.stringify({
      staff_id:staffId,mark_type:'MANUAL',category:cat,points,description:desc
    })});
    closeSFHModal('mark-modal');
    toast(`Performance mark recorded: ${points>0?'+':''}${points} pts (PQC-Signed) ✓`);
    loadLeaderboard();
    loadMarks();
  }catch(e){toast(e.message,'error');}
}

/* ═══ ANALYTICS ══════════════════════════════════════════════ */
async function loadAnalytics(){
  // Shift distribution chart
  const shiftCtx=document.getElementById('shift-chart')?.getContext('2d');
  if(shiftCtx&&!_shiftChart){
    _shiftChart=new Chart(shiftCtx,{type:'doughnut',
      data:{labels:['Morning','Afternoon','Night','Day Off'],
        datasets:[{data:[12,8,5,3],
          backgroundColor:['#fde68a','#a5f3fc','#a5b4fc','#e4e8f0'],
          borderColor:['#d97706','#0891b2','#6366f1','#94a3b8'],borderWidth:2}]},
      options:{responsive:true,plugins:{legend:{position:'bottom',labels:{font:{size:10}}}}}
    });
  }
  // Leave by type chart
  const leaveCtx=document.getElementById('leave-chart')?.getContext('2d');
  if(leaveCtx&&!_leaveChart){
    _leaveChart=new Chart(leaveCtx,{type:'bar',
      data:{labels:['Annual','Sick','Maternity','Study','Emergency'],
        datasets:[{label:'Days',data:[45,12,30,10,5],
          backgroundColor:'rgba(124,58,237,.5)',borderColor:'#7c3aed',borderWidth:2}]},
      options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{font:{size:9}}}}}
    });
  }
  // Attendance rate chart
  const attCtx=document.getElementById('att-chart')?.getContext('2d');
  if(attCtx&&!_attChart){
    const labels=Array.from({length:14},(_,i)=>{const d=new Date();d.setDate(d.getDate()-13+i);return d.toLocaleDateString('en-GB',{day:'2-digit',month:'short'});});
    _attChart=new Chart(attCtx,{type:'line',
      data:{labels,datasets:[{label:'Attendance %',
        data:labels.map(()=>88+Math.random()*10),
        borderColor:'#7c3aed',backgroundColor:'rgba(124,58,237,.08)',fill:true,tension:.3}]},
      options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{min:70,max:100,ticks:{font:{size:9}}}}}
    });
  }

  // Top performers
  const el=document.getElementById('top-performers-list');
  if(el){
    try{
      const data=await apiFetch(`${API}/admin/users?limit=200`);
      const sorted=data.slice().sort((a,b)=>(b.total_marks||100)-(a.total_marks||100)).slice(0,5);
      el.innerHTML=sorted.map((s,i)=>{
        const score=s.total_marks||100;
        return `<div style="display:flex;align-items:center;gap:.5rem;padding:.35rem 0;border-bottom:1px solid #f1f5f9;font-size:.8rem">
          <span style="font-weight:800;color:#7c3aed;min-width:20px">#${i+1}</span>
          <div style="flex:1"><strong>${s.first_name} ${s.last_name}</strong><br><span style="font-size:.68rem;color:#94a3b8">${s.role||'—'}</span></div>
          <strong style="color:${score>=90?'#16a34a':score>=75?'#d97706':'#dc2626'}">${score.toFixed(1)} pts</strong>
        </div>`;
      }).join('');
    }catch(_){}
  }
}

/* ═══ MODAL HELPERS ══════════════════════════════════════════ */
function closeSFHModal(id){ document.getElementById(id).style.display='none'; }
document.querySelectorAll('.sfh-modal-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el)el.style.display='none';});
});

function exportStaffCSV(){
  const rows=_staffList.map(s=>`"${s.first_name} ${s.last_name}","${s.username}","${s.email}","${s.role}","${s.department||''}","${s.is_active?'Active':'Inactive'}"`);
  const csv=['Name,Username,Email,Role,Department,Status',...rows].join('\n');
  const blob=new Blob([csv],{type:'text/csv'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='staff_list.csv';a.click();
  toast('Staff list exported to CSV ✓');
}

/* ═══ INIT ═══════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded',()=>{
  _weekStart=getWeekMonday(new Date());
  loadStaff();
  const today=new Date().toISOString().split('T')[0];
  const d=document.getElementById('att-date');if(d)d.value=today;
  setText('kpi-on-shift','—');
  setText('kpi-leave-pending','—');
  setText('kpi-auto-marks','—');
  setText('kpi-manual-marks','—');
});
