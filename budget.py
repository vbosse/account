#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, Response
from werkzeug.datastructures import ImmutableMultiDict

from datetime import date,datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
                        7:'CREDIT PREVI',
                        8:'DEBIT PREVI',
                        98:'SOLDE CREDIT',
                        99:'SOLDE DEBIT',
                        100:'INCONNU'}

trx_type_credit = {2, 6, 7, 98}

account_init_balances = {'commun' : {'balance':0.0, 'date':'01-01-2015'}, 
                         'charge' : {'balance':0.0, 'date':'01-01-2015'}
                         }

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

        for entry in f_entries:
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
    return dict(format_date=format_date, compute_account_balance=compute_account_balance, account_init_balances=account_init_balances)

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

    if error == '' and request.args.has_key('amount'):
        entry.amount = request.args.get('amount')

    if error == '' and request.args.has_key('type') and trx_type_description.has_key(int(request.args.get('type'))):
        entry.type = int(request.args.get('type'))
    else:
        entry.type = 100

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

    if error == '' and request.args.has_key('amount'):
        entry.amount = request.args.get('amount')

    if error == '' and request.args.has_key('is_checked') and request.args.get('is_checked') == "1":
        entry.is_checked = True
    else:
        entry.is_checked = False
    
    if error == '' and request.args.has_key('type') and trx_type_description.has_key(int(request.args.get('type'))):
        entry.type = int(request.args.get('type'))
    else:
        entry.type = 100

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

    '''Build filters'''
    if request.args.has_key('account_id'):
        account_filter = request.args.getlist('account_id')
    if request.args.has_key('type'):
        type_filter = request.args.getlist('type')
    if request.args.has_key('category'):
        category_filter = request.args.getlist('category')
    if request.args.has_key('edit_filter'):
        edit_filter = map(int,request.args.getlist('edit_filter'))

    query = get_db_session().query(Entry)
    if len(account_filter) != 0:
        query = query.filter(Entry.account_id.in_(account_filter))
    if len(type_filter) != 0:
        query = query.filter(Entry.type.in_(type_filter))
    if len(category_filter) != 0:
        query = query.filter(Entry.category.in_(category_filter))
        
    f_entries = query.order_by(Entry.date.desc()).all()

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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)

