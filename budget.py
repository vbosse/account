#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, Response, make_response
from werkzeug.datastructures import ImmutableMultiDict

from datetime import date,datetime

from sqlalchemy import create_engine
from sqlalchemy import not_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import StatementError
from sqlalchemy.exc import IntegrityError

from budget_db_create import Base, Entry
import json
from dateutil.relativedelta import *
import calendar



app = Flask(__name__)

app.config.update(dict(
    DATABASE='budget.db',
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


trx_type_description = {0:'RETRAIT DAB',
                        1:'FACTURE CARTE',
                        2:'VIR SEPA RECU',
                        3:'PRLV SEPA',
                        4:'ECHEANCE PRET',
                        5:'VIR CPTE A CPTE EMIS',
                        6:'VIR CPTE A CPTE RECU',
                        7:'CREDIT',
                        8:'DEBIT',
                        98:'SOLDE CREDIT',
                        99:'SOLDE DEBIT',
                        100:'INCONNU'}

trx_type_credit = {2, 6, 7, 98}

account_init_balances = {'commun' : {'balance':0.0, 'date':'01-01-2015'},
                         '1A_act' : {'balance':0.0, 'date':'01-01-2015'},
                         '1A_PEE' : {'balance':0.0, 'date':'01-01-2015'},
                         '1A_PEE_d' : {'balance':0.0, 'date':'01-01-2015'},
                         'immo' : {'balance':0.0, 'date':'01-01-2015'},
                         'Em' : {'balance':0.0, 'date':'01-01-2015'},
                         'Th' : {'balance':0.0, 'date':'01-01-2015'},
                         'charge' : {'balance':0.0, 'date':'01-01-2015'}
                        }

account_budgeted = [{'budget':u'essence','max':200.0, 'mode':'m'},
                    {'budget':u'cantine','max':120.0, 'mode':'m'},
                    {'budget':u'voyage','max':3000, 'mode':'y'},
                    {'budget':u'activité','max':2500, 'mode':'y'},
                    {'budget':u'étude Lucie','max':2200, 'mode':'y'},
                    {'budget':u'stages','max':448, 'mode':'y'},
                    {'budget':u'divers','max':1000, 'mode':'y'}]


def compute_monthly_out(s_account, s_category, s_mode='m'):
    TODAY = date.today()
    if s_mode == 'y':
        the_date = date(TODAY.year, TODAY.month, 1)
    else:
        the_date = date(2016,4,1)
    query = get_db_session().query(Entry)
    query = query.filter(Entry.account_id.in_([s_account]))
    query = query.filter(Entry.category.in_([s_category]))
    query = query.filter(Entry.date >= the_date)
    total = 0.0

    f_entries = query.all()
    for entry in f_entries:
        if entry.type in trx_type_credit:
            total += entry.amount
        else:
            total -= entry.amount
    return total
    

def compute_account_balance_v1(s_account, d_date = None):
    if account_init_balances.has_key(s_account):
        balance = account_init_balances[s_account]['balance']
        the_date = datetime.strptime(account_init_balances[s_account]['date'],'%d-%m-%Y')
        query = get_db_session().query(Entry)
        query = query.filter(Entry.account_id.in_([s_account]))
        query = query.filter(Entry.date >= the_date)
        if d_date != None:
            query = query.filter(Entry.date <= d_date)
        f_entries = query.order_by(Entry.date.desc()).all()

        for entry in f_entries:
            if entry.type in trx_type_credit:
                balance += entry.amount
            else:
                balance -= entry.amount
        return balance
    else:
        return -10000.0

def compute_account_balance(s_account, d_date = None):
    if account_init_balances.has_key(s_account):
        balance = account_init_balances[s_account]['balance']
        the_date = datetime.strptime(account_init_balances[s_account]['date'],'%d-%m-%Y')
        query = get_db_session().query(Entry)
        query = query.filter(Entry.account_id.in_([s_account]))
        query = query.filter(Entry.date >= the_date)
        if d_date != None:
            query = query.filter(Entry.date <= d_date)
        f_entries = query.order_by(Entry.date.desc()).all()
        balance_date = None

        for entry in f_entries:
            if entry.type == 98 or entry.type == 99:
                if entry.type == 98:
                    balance = entry.amount
                else:
                    balance = -entry.amount
                balance_date = entry.date
                break
        for entry in f_entries:
            if entry.type < 98 and (balance_date == None or entry.date >= balance_date or not entry.is_checked):
                if entry.type in trx_type_credit:
                    balance += entry.amount
                else:
                    balance -= entry.amount
        return balance
    else:
        return -10000.0


@app.context_processor
def utility_processor():
    def format_date(dDate):
        return dDate.strftime("%d-%m-%Y")
    return dict(format_date=format_date, compute_account_balance=compute_account_balance, account_init_balances=account_init_balances, trx_type_credit = trx_type_credit, account_budgeted=account_budgeted, compute_monthly_out=compute_monthly_out)

def create_db_session():
    """Creates the sql alchemy engine."""
    engine = engine = create_engine('sqlite:///budget.db')
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return session

def get_db_session():
    if not hasattr(g, 'sql_alchemy_session'):
        g.sql_alchemy_session = create_db_session()
    return g.sql_alchemy_session


@app.route("/create/entry")
def create_entry():
    entry = Entry(is_checked=False)
    error = ''

    if error == '' and request.args.has_key('account_id'):
        entry.account_id = request.args.get('account_id')
    else:
        error=u'Pas de compte associé'

    if error == '':
        if request.args.has_key('date') and request.args.get('date') !='' :
            try:
                entry.date = datetime.strptime(request.args.get('date'),'%d-%m-%Y')
            except:
                error=u'Format de date invalide'
        else:
            entry.date = date.today()

    if error == '' and request.args.has_key('description'):
        entry.description = request.args.get('description')

    if error == '' and request.args.has_key('category'):
        entry.category = request.args.get('category')

    if error == '' and request.args.has_key('note_id'):
        entry.note_id = request.args.get('note_id')

    try:
        if error == '' and request.args.has_key('amount_credit') and request.args.get('amount_credit') != '' :
            entry.amount = float(request.args.get('amount_credit'))
            entry.type = 7

        if error == '' and request.args.has_key('amount_debit') and request.args.get('amount_debit') != '':
            entry.amount = float(request.args.get('amount_debit'))
            entry.type = 8
    except:
        error = u'Erreur Technique'

    if entry.amount == None:
        error = u'Erreur Technique'

    if error == '' and request.args.has_key('is_checked') and request.args.get('is_checked') == "1":
        entry.is_checked = True
    else:
        entry.is_checked = False

    if error == '':
        try:
            get_db_session().add(entry)
            get_db_session().commit()
        except:
            error = 'Erreur technique'
    

    if error == '':
        flash(u'Nouvelle transaction enregistrée', 'success')
    else:
        flash(error, 'error')
    return redirect(url_for('show_entry', account_id = entry.account_id))

@app.route("/update/entry")
def update_entry():
    error = ''

    if request.args.has_key('id'):
        try:
            entry = get_db_session().query(Entry).filter(Entry.id == request.args.get('id')).first()
        except:
            error = u'Erreur technique'
    else:
        error=u'Id de la transaction manquante'
        
    if error == '' and request.args.has_key('account_id'):
        entry.account_id = request.args.get('account_id')

    if error == '' and request.args.has_key('date'):
        entry.date = datetime.strptime(request.args.get('date'),'%d-%m-%Y')

    if error == '' and request.args.has_key('description'):
        entry.description = request.args.get('description')

    if error == '' and request.args.has_key('category'):
        entry.category = request.args.get('category')

    if error == '' and request.args.has_key('note_id'):
        entry.note_id = request.args.get('note_id')

    try:
        if error == '' and request.args.has_key('amount_credit') and request.args.get('amount_credit') != '' :
            entry.amount = float(request.args.get('amount_credit'))
            entry.type = 7

        if error == '' and request.args.has_key('amount_debit') and request.args.get('amount_debit') != '':
            entry.amount = float(request.args.get('amount_debit'))
            entry.type = 8
    except:
        error = u'Erreur Technique'
    if entry.amount == None:
        error = u'Erreur Technique'

    if error == '' and request.args.has_key('is_checked') and request.args.get('is_checked') == "1":
        entry.is_checked = True
    else:
        entry.is_checked = False


    if error == '':
        try:
            get_db_session().merge(entry)
            get_db_session().commit()
        except:
            error = u'Erreur technique'
    

    if error == '':
        flash(u'Transaction modifiée', 'success')
    else:
        flash(error, 'error')
    return redirect(url_for('show_entry', account_id = entry.account_id))

@app.route("/check/entry")
def check_entry():
    error = ''
    id_list = []
    account_id = ''
    if request.args.has_key('account_id'):
        account_id =  request.args.get('account_id')
    
    # New balance
    if request.args.has_key('solde') and request.args.get('solde') != '':
        entry = Entry(is_checked=True)
        solde =  float(request.args.get('solde'))
        entry.account_id = account_id
        if solde > 0.0:
            entry.type = 98
            entry.amount = solde
        else:
            entry.type = 99
            entry.amount = -solde
        entry.date = date.today()
        try:
            get_db_session().add(entry)
        except:
            error = u'Erreur technique'

    if request.args.has_key('id'):
        id_list = request.args.getlist('id')
    try:
        f_entries = get_db_session().query(Entry).filter(Entry.id.in_(id_list)).filter(not_(Entry.type.in_([98,99]))).all()
    except:
        error = u'Erreur technique'

    for entry in f_entries:
        if error == '' and request.args.has_key('is_checked_'+str(entry.id)) and request.args.get('is_checked_'+str(entry.id)) == "1":
            entry.is_checked = True
        else:
            entry.is_checked = False

        if error == '' and request.args.has_key('amount_credit_'+str(entry.id)) and request.args.get('amount_credit_'+str(entry.id)) != '' :
            entry.amount = float(request.args.get('amount_credit_'+str(entry.id)))
            entry.type = 7

        if error == '' and request.args.has_key('amount_debit_'+str(entry.id)) and request.args.get('amount_debit_'+str(entry.id)) != '':
            entry.amount = float(request.args.get('amount_debit_'+str(entry.id)))
            entry.type = 8
        try:
            get_db_session().merge(entry)
        except StatementError as e:
            print e
            error = u'Erreur technique'
        except:
            print "Unexpected error 2:", sys.exc_info()[0]
            error = u'Erreur technique'

    if error == '':
        try:
            get_db_session().commit()
        except StatementError as e:
            get_db_session().rollback()
            print e
            error = u'Erreur technique'
        except:
            get_db_session().rollback()
            print "Unexpected error:", sys.exc_info()[0]
            error = u'Erreur technique'
    account_id = ''
    if request.args.has_key('account_id'):
        id_list = request.args.getlist('account_id')
    if len(id_list) == 0:
        id_list.append('commun')

    if error == '':
        flash(u'Transaction modifiée', 'success')
    else:
        flash(error, 'error')
    return redirect(url_for('show_entry', account_id=id_list[0]))


@app.route("/delete/entry")
def delete_entry():
    error = ''
    account_id = ''
    if request.args.has_key('id'):
        try:
            account_id = get_db_session().query(Entry).filter(Entry.id == request.args.get('id')).first().account_id
            entry = get_db_session().query(Entry).filter(Entry.id == request.args.get('id')).delete()
            get_db_session().commit()
        except:
            error = u'Erreur technique'
    else:
        error=u'Id de la transaction manquante'

    if error == '':
        flash(u'Transaction effacée', 'success')
    else:
        flash(error, 'error')
    return redirect(url_for('show_entry',account_id=account_id))
    
@app.route("/show/entry")
def show_entry():
    account_filter=[]
    type_filter=[]
    category_filter=[]
    edit_filter=[]
    unchecked_filter = False

    '''Build filters'''
    if request.args.has_key('account_id'):
        account_filter = request.args.getlist('account_id')
    if request.args.has_key('type'):
        type_filter = request.args.getlist('type')
    if request.args.has_key('category'):
        category_filter = request.args.getlist('category')
    if request.args.has_key('edit_filter'):
        edit_filter = map(int,request.args.getlist('edit_filter'))
    if request.args.has_key('unchecked_filter') and request.args.get('unchecked_filter') == '1':
        unchecked_filter  = True

    query = get_db_session().query(Entry)
    if len(account_filter) != 0:
        query = query.filter(Entry.account_id.in_(account_filter))
    if len(type_filter) != 0:
        query = query.filter(Entry.type.in_(type_filter))
    if len(category_filter) != 0:
        query = query.filter(Entry.category.in_(category_filter))
    if unchecked_filter:
        query = query.filter(Entry.is_checked == False)

    
    f_entries = query.order_by(Entry.date.desc()).filter(not_(Entry.type.in_([98,99]))).all()

    if request.args.has_key('format') and request.args.get('format') == 'json':
        result = {'entries':[]}
        for f_entry in f_entries:
            ret = {'id':f_entry.id, 'account_id':f_entry.account_id, 'date':f_entry.date.strftime("%d%m%y"), 'description':f_entry.description, 'category':f_entry.category, 'note_id':f_entry.note_id, 'amount':f_entry.amount, 'type':f_entry.type, 'type_description':trx_type_description[f_entry.type], 'is_checked':f_entry.is_checked}
            result['entries'].append(ret)
            resp = Response(response=json.dumps(result), status=200, mimetype="application/json")
        return resp
    else:
        if len(account_filter) == 0:
            account_filter.append('commun')
        if unchecked_filter:
            return render_template('budget_check_board.html', entries=f_entries, edit_filter=edit_filter, trx_type_description=trx_type_description, account=account_filter[0])
        else:
            return render_template('budget_board.html', entries=f_entries, edit_filter=edit_filter, trx_type_description=trx_type_description, account=account_filter[0])

@app.route("/summary")
def summary():
    computed_balances = {}
    for key in account_init_balances.keys():
        computed_balances[key] = compute_account_balance(key)
    global_balance = 0.0
    for key in computed_balances.keys():
        global_balance += computed_balances[key]
    # compute balance for the last 12 months
    TODAY = date.today()
    oneyear = TODAY+relativedelta(years=-1)
    oneyear = date(oneyear.year, oneyear.month, 1)
    last_year = []
    for i in range(12):
        temp_computed_balances = {}
        the_date = oneyear+relativedelta(months=+12-i)
        for key in account_init_balances.keys():
            temp_computed_balances[key] = compute_account_balance(key, the_date)
        balance = 0.0
        for key in temp_computed_balances.keys():
            balance += temp_computed_balances[key]
        last_year.append( dict(date=the_date,balance=balance))
    return render_template('budget_summary.html', computed_balances=computed_balances, global_balance = global_balance, last_year=last_year)

@app.route("/custom_csv")
def custom_csv():
    '''Build filters'''
    date_filter = None
    if request.args.has_key('from'):
        try:
            date_filter = datetime.strptime(request.args.get('from'), '%Y%m%d').date()
        except:
            date_filter = None
    query = get_db_session().query(Entry)    
    query.filter(Entry.account_id.in_('commun'))
    if date_filter != None:
        query.filter(Entry.date >= date_filter)
    f_entries = query.order_by(Entry.date.desc()).all()
    data = []
    for entry in f_entries:
        a_row = []
        if entry.date >= date_filter:
            a_row.append(str(entry.date))
            if entry.description != None:
                a_row.append(entry.description)
            else:
                a_row.append('')
            if entry.note_id != None:
                a_row.append(entry.note_id)
            else:
                a_row.append('')
            if entry.type not in trx_type_credit:
                a_row.append(str(entry.amount).replace('.',','))
            else:
                a_row.append('')
            if entry.type in trx_type_credit:
                a_row.append(str(entry.amount).replace('.',','))
            else:
                a_row.append('')
            if entry.is_checked:
                a_row.append('ok')
            else:
                a_row.append('')
            data.append(a_row)
    output_file = ''
    for entry in data:
        for column in entry:
            output_file+=column+'\t'
        output_file+='\n'
    output = make_response(output_file)
    output.headers["Content-Disposition"] = "attachment; filename=export_1.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)

