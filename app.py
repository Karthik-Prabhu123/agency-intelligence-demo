"""Public, synthetic-only Agency Intelligence showcase, using original V1.3.1 diagnostics."""
import io
import math
import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, Image, HRFlowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import plotly.graph_objects as go
import re
from xml.sax.saxutils import escape
import campaign_intelligence as ci

st.set_page_config(page_title="Agency Intelligence | Interactive Demo", page_icon="📊", layout="wide")
st.markdown("""<style>
.block-container{max-width:1600px;padding:1.2rem 2.5rem 3rem}
[data-testid='stMetric']{background:#fff;border:1px solid #dfe6f0;border-radius:14px;padding:15px}
h1,h2,h3{letter-spacing:-.025em}div[data-testid='stTabs'] button{font-size:.9rem}
[data-testid='stSidebar']{background:#f3f6fb}
</style>""",unsafe_allow_html=True)

CLIENTS={
"Northstar Commerce · E-commerce": {"currency":"USD","rows":[
("Meta","BOF_Retargeting_Purchase",650,25,2470), ("Meta","TOF_Lookalike_Prospecting",450,12,855), ("Meta","MOF_Engagement",150,0,0),
("Google","Search_Brand_Alpha",350,45,1520), ("Google","PerformanceMax_US",420,18.5,1280), ("Google","Display_Remarketing",80,2,90)]},
"UrbanNest Services · Lead generation": {"currency":"INR","rows":[
("Meta","Local_Lead_Form",22000,90,65000),("Meta","Retargeting_Leads",12500,35,40000),("Meta","Awareness_Creative",9500,0,0),
("Google","High_Intent_Search",31000,110,124000),("Google","Competitor_Search",16500,25,35000),("Google","Display_Prospecting",7500,6,5500)]},
"Luma Learning · Education": {"currency":"INR","rows":[
("Meta","Course_Launch",18000,28,56000),("Meta","Webinar_Signups",9000,45,27000),("Meta","Cold_Audience_Test",11000,3,3500),
("Google","Course_Search",24500,52,130000),("Google","Brand_Search",6000,30,45000),("Google","YouTube_Awareness",8000,0,0)]}}

def get_data(client):
    info=CLIENTS[client]
    frame=pd.DataFrame(info['rows'],columns=['platform','campaign','spend','conversions','revenue'])
    frame['clicks']=float('nan');frame['impressions']=float('nan')
    frame['clicks_available']=False;frame['impressions_available']=False
    return frame

def money(x,currency):
    return f"{'₹' if currency=='INR' else '$'}{x:,.2f}"

def safe_number(x,digits=2):
    return f'{x:,.{digits}f}' if pd.notna(x) and math.isfinite(float(x)) else 'N/A'


DISPLAY_NAMES={
'BOF_Retargeting_Purchase':'Meta · Retargeting','TOF_Lookalike_Prospecting':'Meta · Prospecting',
'MOF_Engagement':'Meta · Engagement','Search_Brand_Alpha':'Google · Brand Search',
'PerformanceMax_US':'Google · Performance Max','Display_Remarketing':'Google · Remarketing',
'Local_Lead_Form':'Meta · Local Lead Form','Retargeting_Leads':'Meta · Lead Retargeting',
'Awareness_Creative':'Meta · Awareness','High_Intent_Search':'Google · High-intent Search',
'Competitor_Search':'Google · Competitor Search','Display_Prospecting':'Google · Display Prospecting',
'Course_Launch':'Meta · Course Launch','Webinar_Signups':'Meta · Webinar Signups',
'Cold_Audience_Test':'Meta · Cold Audience','Course_Search':'Google · Course Search',
'Brand_Search':'Google · Brand Search','YouTube_Awareness':'Google · YouTube Awareness'}
def display_name(raw): return DISPLAY_NAMES.get(str(raw),str(raw).replace('_',' '))
def plain_money(v,currency): return ('INR ' if currency=='INR' else '$')+f'{float(v):,.2f}'
def roas_fmt(v):return f'{float(v):.2f}x' if pd.notna(v) else 'N/A'
def action_for(row):
    name=str(row['Campaign']).lower(); priority=row['Priority']
    if priority=='High':
        if 'awareness' in name or 'engagement' in name:
            return 'Confirm whether this campaign is intended to drive direct conversions; verify event tracking and attribution, then review reach, engagement and assisted outcomes before changing spend.'
        return 'Audit conversion events and reporting period; check landing-page experience, audience quality and placements before considering a limited budget test.'
    if priority=='Medium':return 'Compare CPA against similar campaigns with the same conversion objective, then review audience, bidding and creative before a controlled change.'
    if 'brand' in name:return 'Check impression share, brand demand and incremental lift. High brand-search ROAS alone does not establish room to scale.'
    if 'retarget' in name:return 'Review audience pool size, frequency and conversion overlap; test a modest increase only if incremental demand exists.'
    if 'performance' in name:return 'Inspect asset groups, search themes and conversion quality where available; test a gradual increase and monitor marginal CPA.'
    if 'lead' in name:return 'Validate qualified-lead rate and sales follow-up capacity before expanding spend; monitor cost per qualified lead.'
    return 'Check contribution margin, conversion quality and available audience demand; test budget changes incrementally and monitor marginal results.'
def executive_brief(client,summary,findings,currency):
    sp=float(summary.spend.sum());rv=float(summary.revenue.sum()); n=len(summary)
    high=findings[findings.Priority=='High'] if not findings.empty else pd.DataFrame()
    opp=findings[findings.Priority=='Opportunity'] if not findings.empty else pd.DataFrame()
    lead=f'{client.split(" · ")[0]} recorded {plain_money(rv,currency)} in platform-attributed value against {plain_money(sp,currency)} in spend across {n} campaigns (reported blended ROAS {rv/sp:.2f}x). These are platform-reported figures, not verified net revenue.'
    if not high.empty:
        h=high.iloc[0]; lead+=f' The first investigation is {display_name(h.Campaign)}, with {plain_money(h["Spend without conversions"],currency)} spent and no reported conversions.'
    if not opp.empty: lead+=f' {len(opp)} campaigns meet the current opportunity-screening criteria, subject to margin, attribution and capacity checks.'
    return lead

def pdf_report(client,currency,summary,findings,agency,preparer,period,include_details=True):
    buff=io.BytesIO()
    navy=colors.HexColor('#172d50'); teal=colors.HexColor('#0b8278'); pale=colors.HexColor('#eef4fa'); muted=colors.HexColor('#51627b')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitleCustom',fontName='Helvetica-Bold',fontSize=20,leading=25,textColor=navy,spaceAfter=8))
    styles.add(ParagraphStyle(name='SectionCustom',fontName='Helvetica-Bold',fontSize=12.5,leading=17,textColor=navy,spaceBefore=14,spaceAfter=8,keepWithNext=True))
    styles.add(ParagraphStyle(name='BodyCustom',fontName='Helvetica',fontSize=9,leading=14,textColor=navy,spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallCustom',fontName='Helvetica',fontSize=7.5,leading=11,textColor=muted,spaceAfter=6))
    styles.add(ParagraphStyle(name='TableCustom',fontName='Helvetica',fontSize=7.5,leading=10,textColor=navy))
    doc=SimpleDocTemplate(buff,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=48,bottomMargin=46,title='Agency Intelligence | Synthetic Client Report')
    W=A4[0]-76
    def para(t,sty='BodyCustom'):return Paragraph(escape(str(t)),styles[sty])
    def cell(t):return para(t,'TableCustom')
    def tbl(rows,widths,header=True):
        t=Table(rows,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
        cmds=[('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#dce5ef'))]
        if header:cmds += [('BACKGROUND',(0,0),(-1,0),pale),('TEXTCOLOR',(0,0),(-1,0),navy),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')])]
        t.setStyle(TableStyle(cmds));return t
    story=[para('AGENCY INTELLIGENCE','SmallCustom'),para('Client Performance Report','ReportTitleCustom'),
           para(f'{client}  |  {period}','BodyCustom'),HRFlowable(width='100%',thickness=1,color=teal),Spacer(1,12),
           para(f'Prepared for: {client}     |     Agency: {agency}     |     Prepared by: {preparer}','SmallCustom'),
           para('01  |  Executive performance summary','SectionCustom')]
    sp=float(summary.spend.sum()); rv=float(summary.revenue.sum());conv=float(summary.conversions.sum())
    cards=[[cell('AD SPEND'),cell('REPORTED CONVERSIONS'),cell('ATTRIBUTED VALUE'),cell('REPORTED ROAS')],
           [cell(plain_money(sp,currency)),cell(f'{conv:,.1f}'),cell(plain_money(rv,currency)),cell(f'{rv/sp:.2f}x')]]
    story.extend([tbl(cards,[W/4]*4,False),Spacer(1,12),para(executive_brief(client,summary,findings,currency)),
                  para('Performance by platform','SectionCustom')])
    plat=summary.groupby('platform',as_index=False)[['spend','conversions','revenue']].sum()
    prows=[[cell(x) for x in ['Platform','Spend','Conversions','Attributed value','ROAS']]]
    for _,r in plat.iterrows():prows.append([cell(r.platform),cell(plain_money(r.spend,currency)),cell(f'{r.conversions:,.1f}'),cell(plain_money(r.revenue,currency)),cell(roas_fmt(r.revenue/r.spend if r.spend else float('nan')))])
    story.extend([tbl(prows,[W*.17,W*.21,W*.18,W*.27,W*.17]),Spacer(1,10)])
    high=findings[findings.Priority=='High'] if not findings.empty else pd.DataFrame()
    opp=findings[findings.Priority=='Opportunity'] if not findings.empty else pd.DataFrame()
    story.append(para('What deserves attention','SectionCustom'))
    if high.empty:story.append(para('No high-priority rules triggered at the selected screening thresholds.'))
    else:
        for _,r in high.head(2).iterrows():story.append(para(f'Investigate {display_name(r.Campaign)}: {plain_money(r["Spend without conversions"],currency)} spent without reported conversions ({r["Spend share"]:.1f}% of account spend).'))
    story.append(para(f'{len(opp)} potential scaling candidates met the screening rules. These are opportunities for controlled tests, not instructions to increase budgets.'))
    story.append(para('02  |  Campaign performance','SectionCustom'))
    rows=[[cell(x) for x in ['Campaign','Spend','Conv.','ROAS','CPA']]]
    for _,r in summary.iterrows():rows.append([cell(display_name(r.campaign)),cell(plain_money(r.spend,currency)),cell(f'{r.conversions:,.1f}'),cell(roas_fmt(r.roas)),cell(plain_money(r.cpa,currency) if pd.notna(r.cpa) else 'N/A')])
    story.extend([tbl(rows,[W*.37,W*.19,W*.12,W*.13,W*.19]),Spacer(1,12)])
    # Simple PDF-native bar chart; no external image dependencies.
    from reportlab.graphics.shapes import Drawing, Rect, String
    drawing=Drawing(W,132)
    max_sp=float(summary.spend.max()) if len(summary) else 1
    ordered=summary.sort_values('spend',ascending=False).head(6)
    for i,(_,r) in enumerate(ordered.iterrows()):
        y=112-i*20; bar_w=190*float(r.spend)/max_sp
        drawing.add(String(3,y+3,display_name(r.campaign)[:29],fontName='Helvetica',fontSize=7.5,fillColor=navy))
        drawing.add(Rect(205,y,bar_w,11,fillColor=teal if r.platform=='Google' else colors.HexColor('#4278c5'),strokeColor=None))
        drawing.add(String(405,y+2,plain_money(r.spend,currency),fontName='Helvetica',fontSize=7,fillColor=navy))
    story.extend([para('Spend by campaign','SectionCustom'),drawing,Spacer(1,10)])
    story.append(para('03  |  Prioritized review plan','SectionCustom'))
    if findings.empty:story.append(para('No screening findings at the current thresholds; review campaign objectives and source quality before drawing conclusions.'))
    else:
        for idx,(_,r) in enumerate(findings.head(6).iterrows(),1):
            story.append(KeepTogether([para(f'{idx}. {display_name(r.Campaign)} — {r.Priority} | {r.Finding}','SectionCustom'),
               para(f'Evidence: {r.Evidence}'),para(f'Next review: {action_for(r)}')]))
    story.extend([Spacer(1,8),para('Data quality and interpretation','SectionCustom'),
      para('Synthetic demonstration only. Figures are platform-attributed and may overlap across channels; they are not deduplicated revenue or profit. No clicks, impressions or dated trend history are supplied in this sample. Campaign objectives, tracking, margins and incrementality must be validated before budget decisions.','SmallCustom')])
    def footer(canv,document):
        canv.saveState();canv.setStrokeColor(colors.HexColor('#dce5ef'));canv.line(38,35,A4[0]-38,35)
        canv.setFont('Helvetica',7);canv.setFillColor(muted);canv.drawString(38,24,'Agency Intelligence  |  Synthetic demonstration  |  Not financial advice')
        canv.drawRightString(A4[0]-38,24,f'Page {document.page}');canv.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buff.getvalue()

with st.sidebar:
    st.title('◈ Agency Intelligence')
    st.caption('Interactive product showcase · fictional data only')
    client=st.selectbox('Demo client',list(CLIENTS))
    currency=CLIENTS[client]['currency']
    st.divider();st.subheader('Screening controls')
    target=st.number_input('Target ROAS',min_value=0.1,max_value=30.0,value=2.0,step=0.1)
    min_spend=st.number_input(f'Minimum alert spend ({currency})',min_value=0.0,max_value=1000000.0,value=50.0 if currency=='USD' else 5000.0,step=10.0 if currency=='USD' else 500.0)
    min_conv=st.number_input('Minimum conversions for scaling',min_value=1.0,max_value=1000.0,value=5.0,step=1.0)
    st.divider();st.caption('Read-only fictional datasets. No uploads, login, database writes or external AI requests.')

data=get_data(client)
summary,findings,notes=ci.analyse_campaigns(data,target_roas=target,minimum_spend=min_spend,minimum_conversions_for_scale=min_conv)
spend=float(summary.spend.sum());revenue=float(summary.revenue.sum());conversions=float(summary.conversions.sum())
platforms=summary.groupby('platform',as_index=False)[['spend','conversions','revenue']].sum()
platforms['ROAS']=platforms.revenue/platforms.spend
platforms['CPA']=platforms.spend/platforms.conversions.where(platforms.conversions>0)

def formatted_campaigns(frame):
    out=frame[['platform','campaign','spend','conversions','revenue','roas','cpa','spend_share_pct']].copy()
    out['campaign']=out.campaign.map(display_name)
    for col in ['spend','revenue','cpa']:out[col]=out[col].map(lambda v:plain_money(v,currency) if pd.notna(v) else 'N/A')
    out['roas']=out.roas.map(roas_fmt)
    out['conversions']=out.conversions.map(lambda v:f'{v:,.1f}')
    out['spend_share_pct']=out.spend_share_pct.map(lambda v:f'{v:.1f}%')
    return out.rename(columns={'platform':'Platform','campaign':'Campaign','spend':'Spend','conversions':'Conversions','revenue':'Attributed value','roas':'ROAS','cpa':'CPA','spend_share_pct':'Share of spend'})

def horizontal_chart(frame,metric,title):
    temp=frame.copy().sort_values(metric,ascending=True)
    temp['label']=temp.campaign.map(display_name)
    fig=px.bar(temp,x=metric,y='label',color='platform',orientation='h',title=title,
               color_discrete_map={'Meta':'#4776c4','Google':'#159e94'},labels={'label':'','spend':'Spend','revenue':'Attributed value','roas':'ROAS','cpa':'CPA','conversions':'Conversions'})
    fig.update_layout(height=max(330,45*len(temp)+90),margin=dict(l=10,r=15,t=55,b=20),legend_title_text='',yaxis={'categoryorder':'array','categoryarray':temp.label.tolist()})
    return fig

st.title('📊 Agency Intelligence')
st.caption('Performance analytics · Campaign diagnostics · Client-ready reporting')
st.info('PUBLIC DEMO  |  All clients and campaigns are fictional. Diagnostics use the original V1.3.1 rules. AI commentary is an illustrative deterministic preview, not a live LLM response.')
tabs=st.tabs(['Executive Overview','Campaign Analytics','Campaign Intelligence','Intelligence Brief','Report Studio','About the Product'])

with tabs[0]:
    c=st.columns(4)
    for col,label,value in zip(c,['Ad spend','Reported conversions','Platform-attributed value','Blended reported ROAS'],[plain_money(spend,currency),f'{conversions:,.1f}',plain_money(revenue,currency),f'{revenue/spend:.2f}x']):col.metric(label,value)
    st.subheader('Platform performance')
    plat_display=platforms.copy()
    plat_display['Spend']=plat_display.spend.map(lambda x:plain_money(x,currency));plat_display['Conversions']=plat_display.conversions.map(lambda x:f'{x:,.1f}')
    plat_display['Attributed value']=plat_display.revenue.map(lambda x:plain_money(x,currency));plat_display['ROAS']=plat_display.ROAS.map(roas_fmt)
    plat_display['CPA']=plat_display.CPA.map(lambda x:plain_money(x,currency) if pd.notna(x) else 'N/A')
    st.dataframe(plat_display[['platform','Spend','Conversions','Attributed value','ROAS','CPA']].rename(columns={'platform':'Platform'}),hide_index=True,use_container_width=True)
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(horizontal_chart(summary,'spend','Campaign spend'),use_container_width=True)
    with c2:st.plotly_chart(horizontal_chart(summary,'revenue','Attributed conversion value'),use_container_width=True)
    st.caption('Cross-platform attributed values may overlap. Reported ROAS is not verified business profit.')

with tabs[1]:
    st.subheader('Campaign performance explorer')
    c1,c2=st.columns(2)
    with c1: selected_platforms=st.multiselect('Platforms',['Meta','Google'],default=['Meta','Google'])
    with c2: metric=st.selectbox('Compare campaigns by',options=['spend','roas','cpa','conversions','revenue'],format_func=lambda x:{'spend':'Spend','roas':'ROAS','cpa':'CPA','conversions':'Conversions','revenue':'Attributed value'}[x])
    filtered=summary[summary.platform.isin(selected_platforms)].sort_values(metric,ascending=(metric=='cpa'))
    if filtered.empty:st.warning('Select at least one platform to see campaign results.')
    else:
        top=filtered.loc[filtered.roas.idxmax()] if filtered.roas.notna().any() else None
        low=filtered[filtered.cpa.notna()]
        c=st.columns(3)
        c[0].metric('Highest ROAS',roas_fmt(top.roas) if top is not None else 'N/A')
        c[1].metric('Lowest CPA',plain_money(low.cpa.min(),currency) if not low.empty else 'N/A')
        c[2].metric('Campaigns in view',len(filtered))
        st.dataframe(formatted_campaigns(filtered),hide_index=True,use_container_width=True)
        chart_data=filtered[filtered[metric].notna()]
        if not chart_data.empty:st.plotly_chart(horizontal_chart(chart_data,metric,f'Campaign comparison · {metric.upper()}'),use_container_width=True)
    st.download_button('Download campaign table (CSV)',filtered.to_csv(index=False),file_name='synthetic_campaigns.csv',mime='text/csv')
    st.caption('Clicks, impressions, CTR and CPC are unavailable in these samples and are not fabricated.')

with tabs[2]:
    st.subheader('Evidence-led campaign diagnostics')
    high=findings[findings.Priority=='High'] if not findings.empty else pd.DataFrame()
    medium=findings[findings.Priority=='Medium'] if not findings.empty else pd.DataFrame()
    opp=findings[findings.Priority=='Opportunity'] if not findings.empty else pd.DataFrame()
    c=st.columns(4)
    for col,label,value in zip(c,['Campaigns reviewed','High-priority alerts','Efficiency alerts','Scale candidates'],[len(summary),len(high),len(medium),len(opp)]):col.metric(label,value)
    flagged=float(high['Spend without conversions'].sum()) if not high.empty else 0.0
    if flagged:st.error(f'Priority investigation: {plain_money(flagged,currency)} spent without reported conversions ({flagged/spend*100:.1f}% of account spend). This is not confirmed wasted budget.')
    if not opp.empty:
        st.markdown('#### Opportunities worth evaluating')
        for _,r in opp.iterrows():
            st.write(f'**{display_name(r.Campaign)}**  ·  {roas_fmt(r.ROAS)} ROAS  ·  {r.Conversions:,.1f} conversions  ·  {plain_money(r.Spend,currency)} spend')
    st.markdown('#### Detailed evidence and next reviews')
    if findings.empty:st.success('No diagnostic rules triggered at the current thresholds.')
    for _,r in findings.iterrows():
        with st.expander(f'{r.Priority}  |  {display_name(r.Campaign)}  |  {r.Finding}',expanded=r.Priority=='High'):
            st.write('**Evidence:**',r.Evidence)
            st.write('**Recommended next review:**',action_for(r))
            st.caption(f'Share of spend: {r["Spend share"]:.1f}% · Spend without reported conversions: {plain_money(r["Spend without conversions"],currency)}')
    with st.expander('Data quality and interpretation notes'):
        for note in notes:st.info(note)
    st.download_button('Download findings (CSV)',findings.to_csv(index=False),file_name='synthetic_diagnostics.csv',mime='text/csv')

with tabs[3]:
    st.subheader('Executive intelligence brief')
    st.warning('Illustrative deterministic analysis of fictional data. No Groq or other external LLM is called.')
    st.markdown('#### Performance in context')
    st.write(executive_brief(client,summary,findings,currency))
    if findings.empty:st.info('No screening signals at these thresholds; this is not a guarantee of campaign health.')
    else:
        st.markdown('#### Prioritized action sequence')
        for idx,(_,r) in enumerate(findings.head(6).iterrows(),1):
            st.markdown(f'**{idx}. {display_name(r.Campaign)} — {r.Priority}**')
            st.write(action_for(r))
    st.caption('These suggestions are hypotheses for human review. The private prototype includes separate Groq-assisted commentary.')

with tabs[4]:
    st.subheader('Branded client report studio')
    c1,c2=st.columns(2)
    with c1:
        agency=st.text_input('Agency name',value='Your Agency',max_chars=70)
        preparer=st.text_input('Prepared by',value='Performance Team',max_chars=70)
    with c2:
        period=st.text_input('Reporting period',value='Sample 30-day period',max_chars=70)
        st.caption(f'Client: {client}  ·  Currency: {currency}')
    st.caption('Fields are used only to generate an in-memory sample PDF. Do not enter personal or confidential information.')
    st.markdown('#### On-screen report preview')
    st.write(executive_brief(client,summary,findings,currency))
    c=st.columns(3)
    c[0].metric('Spend',plain_money(spend,currency));c[1].metric('Attributed value',plain_money(revenue,currency));c[2].metric('ROAS',f'{revenue/spend:.2f}x')
    st.dataframe(formatted_campaigns(summary),hide_index=True,use_container_width=True)
    try:
        content=pdf_report(client,currency,summary,findings,agency or 'Demo Agency',preparer or 'Performance Team',period or 'Sample period')
        st.download_button('Download professional sample PDF',content,file_name='agency_intelligence_v2_1_sample_report.pdf',mime='application/pdf',type='primary')
    except Exception as exc:st.error(f'Unable to generate PDF: {type(exc).__name__}: {exc}')

with tabs[5]:
    st.subheader('What Agency Intelligence demonstrates')
    st.markdown("""**Public showcase:** Three fictional clients, campaign analytics, the original rule-based diagnostics, evidence-led interpretation, and an in-memory branded PDF.\n\n**Private V1.3.1 prototype:** Meta/Google export ingestion, client workspaces with local SQLite persistence, Groq-assisted narrative generation and reporting.\n\n**Not available in this public demo:** real client uploads, authentication, persistent storage, live ad-platform API integrations or live LLM calls. A security-reviewed private pilot is required before handling real agency data.""")
    st.caption('Screening criteria are configurable. All financial findings require verification against campaign objectives, attribution settings and business outcomes.')
