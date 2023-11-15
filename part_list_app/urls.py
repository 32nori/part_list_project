from django.urls import path
from part_list_app import views

app_name = 'part_list_app'
urlpatterns = [
    # 構成一覧画面
    path('composition/', views.ProductList.as_view(),
         name='product_list'),   # 一覧
    path('composition/search/', views.ProductList.as_view(),
         name='product_search'),   # 検索
    path('composition/del/', views.product_del, name='product_del'),   # 削除

    # 構成を追加画面
    path('composition/add/', views.composition_edit,
         name='composition_add'),  # 追加
    path('composition/add/product/', views.composition_add_product,
         name='composition_add_product'),  # 製品挿入
    path('composition/add/<int:product_id>/add/', views.composition_edit_add,
         name='composition_product_add'),  # 挿入
    path('composition/add/<int:product_id>/addChildren/',
         views.composition_edit_add_children,
         name='composition_add_add_children'),  # 子の挿入
    path('composition/add/<int:product_id>/mod/', views.composition_edit_mod,
         name='composition_add_mod'),  # 変更
    path('composition/add/<int:product_id>/del/', views.composition_edit_del,
         name='composition_add_del'),  # 削除
    path('composition/add/<int:product_id>/drop/', views.composition_edit_drop,
         name='composition_add_drop'),  # ドロップイベント
    path('composition/add/<int:product_id>/undo/', views.composition_edit_undo,
         name='composition_add_undo'),  # 元に戻す
    path('composition/add/<int:product_id>/redo/', views.composition_edit_redo,
         name='composition_add_redo'),  # やり直し

    # 構成を変更画面
    path('composition/mod/<int:product_id>/', views.composition_edit,
         name='composition_mod'),  # 変更
    path('composition/mod/<int:product_id>/add/', views.composition_edit_add,
         name='composition_mod_add'),  # 挿入
    path('composition/mod/<int:product_id>/addChildren/',
         views.composition_edit_add_children,
         name='composition_mod_add_children'),  # 子の挿入
    path('composition/mod/<int:product_id>/mod/', views.composition_edit_mod,
         name='composition_mod_mod'),  # 変更
    path('composition/mod/<int:product_id>/del/', views.composition_edit_del,
         name='composition_mod_del'),  # 削除
    path('composition/mod/<int:product_id>/drop/', views.composition_edit_drop,
         name='composition_mod_drop'),  # ドロップイベント
    path('composition/mod/<int:product_id>/undo/', views.composition_edit_undo,
         name='composition_mod_undo'),  # 元に戻す
    path('composition/mod/<int:product_id>/redo/', views.composition_edit_redo,
         name='composition_mod_redo'),  # やり直し

]
